import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import serial.tools.list_ports

# ---------------------------------------------------------------------------------
# DEBUG MODE
# ---------------------------------------------------------------------------------
DEBUG_MODE = False

# ---------------------------------------------------------------------------------
# CRC configuration (CRC-32, poly=0x04C11DB7, no reflection, no final XOR)
# ---------------------------------------------------------------------------------
from crc import Calculator, Configuration

config = Configuration(
    width=32,
    polynomial=0x04C11DB7,
    init_value=0xFFFFFFFF,
    final_xor_value=0,
    reverse_input=False,
    reverse_output=False,
)
crc_calculator = Calculator(config)

HEADER    = [0xAA, 0x55]
FOOTER    = [0xBB, 0x66]
REQ_BYTE  = 0x01
MAX_CHUNK = 0xFF

def _build_simple_packet(cmd: int) -> bytes:
    body = [cmd, REQ_BYTE, 0]
    to_crc = b''.join(b.to_bytes(4, 'big') for b in body)
    crc    = crc_calculator.checksum(to_crc)
    return bytes(HEADER + body) + crc.to_bytes(4, 'big') + bytes(FOOTER)

def _build_with_payload(cmd: int, data: bytes) -> bytes:
    length = len(data) & 0xFF
    body   = [cmd, REQ_BYTE, length] + list(data)
    to_crc = b''.join(b.to_bytes(4, 'big') for b in body)
    crc    = crc_calculator.checksum(to_crc)
    return bytes(HEADER + body) + crc.to_bytes(4, 'big') + bytes(FOOTER)

COMMAND_CODES = {
    'Connect'    : 0xA0,
    'Disconnect' : 0xA1,
    'Write_FW'   : 0xA3,
    'Read_FW'    : 0xA4,
    'Erase_FW'   : 0xA5,
    'Reboot'     : 0xA6,
}

class BootloaderGUI(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        master.title("STM32F407 Bootloader GUI" + (" [DEBUG]" if DEBUG_MODE else ""))
        master.resizable(False, False)
        self.grid(sticky="nsew")

        self.ser = None
        self.firmware_data = b""

        # Serial Port Frame
        pf = ttk.LabelFrame(self, text="Serial Port Configuration", padding=10)
        pf.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        pf.columnconfigure(1, weight=1)

        ttk.Label(pf, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_cb = ttk.Combobox(pf, values=self._list_ports(), state="readonly", width=15)
        self.port_cb.grid(row=0, column=1, padx=5, sticky="w")
        self.port_cb.set("Select Port")

        ttk.Label(pf, text="Baud Rate:").grid(row=0, column=2, sticky="w", padx=(20,0))
        self.baud_cb = ttk.Combobox(
            pf,
            values=["9600", "19200", "38400", "57600", "115200", "256000"],
            state="readonly",
            width=12
        )
        self.baud_cb.grid(row=0, column=3, padx=5, sticky="w")
        self.baud_cb.set("115200")

        ttk.Button(pf, text="Refresh", command=self._refresh_ports).grid(row=0, column=4, padx=5)
        self.open_btn  = ttk.Button(pf, text="Open Port",  command=self.open_port)
        self.open_btn.grid(row=0, column=5, padx=5)
        self.close_btn = ttk.Button(pf, text="Close Port", command=self.close_port, state="disabled")
        self.close_btn.grid(row=0, column=6, padx=5)

        # Device Frame & Info Fields
        df = ttk.LabelFrame(self, text="Device Configuration", padding=10)
        df.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        df.columnconfigure((0,1), weight=1)

        self.connect_btn    = ttk.Button(df, text="Connect",    command=self.connect_device,    state="disabled")
        self.disconnect_btn = ttk.Button(df, text="Disconnect", command=self.disconnect_device, state="disabled")
        self.connect_btn.grid(row=0, column=0, padx=5, pady=5)
        self.disconnect_btn.grid(row=0, column=1, padx=5)

        # Info variables
        self.bl_ver_var  = tk.StringVar(value="N/A")
        self.fw_ver_var  = tk.StringVar(value="N/A")
        self.pid_var     = tk.StringVar(value="N/A")
        self.pver_var    = tk.StringVar(value="N/A")
        self.appver_var  = tk.StringVar(value="N/A")

        labels = [
            ("Bootloader Ver:", self.bl_ver_var),
            ("Firmware Ver:",   self.fw_ver_var),
            ("Product ID:",     self.pid_var),
            ("Product Ver:",    self.pver_var),
            ("App Ver:",        self.appver_var),
        ]
        for i,(txt,var) in enumerate(labels, start=1):
            ttk.Label(df, text=txt).grid(row=i, column=0, sticky="e", padx=5, pady=2)
            ttk.Entry(df, textvariable=var, width=20, state="readonly")\
               .grid(row=i, column=1, sticky="w", padx=5, pady=2)

        # Operations Frame
        of = ttk.LabelFrame(self, text="Bootloader Operations", padding=10)
        of.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        of.columnconfigure(tuple(range(4)), weight=1)

        ttk.Button(of, text="Browse Firmware", command=self.browse_file).grid(row=0, column=0, padx=5, pady=5)
        self.write_btn  = ttk.Button(of, text="Write FW", command=self.write_firmware, state="disabled")
        self.read_btn   = ttk.Button(of, text="Read FW",  command=self.read_firmware,  state="disabled")
        self.erase_btn  = ttk.Button(of, text="Erase FW", command=self.erase_firmware, state="disabled")
        self.reboot_btn = ttk.Button(of, text="Reboot",   command=self.reboot_mcu,     state="disabled")

        self.write_btn.grid(row=1, column=0, padx=5)
        self.read_btn.grid( row=1, column=1, padx=5)
        self.erase_btn.grid(row=1, column=2, padx=5)
        self.reboot_btn.grid(row=1, column=3, padx=5)

        # Hex View Frame
        hf = ttk.LabelFrame(self, text="Firmware Hex View", padding=10)
        hf.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        cols = ["Addr"] + [f"{n:X}" for n in range(16)]
        self.hex_tree = ttk.Treeview(hf, columns=cols, show="headings", height=8)
        for c in cols:
            self.hex_tree.heading(c, text=c)
            self.hex_tree.column(c, width=50, anchor="center")
        self.hex_tree.grid(row=0, column=0, sticky="nsew")
        sbv = ttk.Scrollbar(hf, orient="vertical", command=self.hex_tree.yview)
        sbv.grid(row=0, column=1, sticky="ns")
        self.hex_tree.configure(yscrollcommand=sbv.set)
        hf.rowconfigure(0, weight=1)
        hf.columnconfigure(0, weight=1)

        # Log Frame
        lf = ttk.LabelFrame(self, text="Log", padding=10)
        lf.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0,10))
        self.log = tk.Text(lf, width=80, height=8, state="disabled", wrap="none")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb2 = ttk.Scrollbar(lf, orient="vertical",   command=self.log.yview)
        sb2.grid(row=0, column=1, sticky="ns")
        sb3 = ttk.Scrollbar(lf, orient="horizontal", command=self.log.xview)
        sb3.grid(row=1, column=0, sticky="ew")
        self.log.configure(yscrollcommand=sb2.set, xscrollcommand=sb3.set)
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)

        master.columnconfigure(0, weight=1)
        master.rowconfigure(3, weight=1)
        master.rowconfigure(4, weight=1)

    def _list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def _refresh_ports(self):
        self.port_cb['values'] = self._list_ports()
        self._log("Ports refreshed")

    def open_port(self):
        port = self.port_cb.get()
        if port in ("", "Select Port"):
            messagebox.showwarning("Please select a COM port first")
            return
        try:
            self.ser = serial.Serial(port, int(self.baud_cb.get()), timeout=1)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._log(f"Opened {port}")
        self.open_btn.config(state="disabled")
        self.close_btn.config(state="normal")
        self.connect_btn.config(state="normal")

    def close_port(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self._log("Port closed")
        self.open_btn.config(state="normal")
        self.close_btn.config(state="disabled")
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="disabled")
        for btn in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn):
            btn.config(state="disabled")

    def browse_file(self):
        fn = filedialog.askopenfilename(title="Select .bin", filetypes=[("BIN","*.bin")])
        if not fn:
            return
        with open(fn, "rb") as f:
            self.firmware_data = f.read()
        full_crc = crc_calculator.checksum(
            b''.join(b.to_bytes(4, 'big') for b in self.firmware_data)
        )
        self._log(f"Full CRC32 = 0x{full_crc:08X}")
        self.hex_tree.delete(*self.hex_tree.get_children())
        for i in range(0, len(self.firmware_data), 16):
            chunk = self.firmware_data[i:i+16]
            row   = [f"{i:08X}"] + [f"{b:02X}" for b in chunk]
            row  += [""] * (17 - len(row))
            self.hex_tree.insert("", "end", values=row)
        self._log(f"Loaded {len(self.firmware_data)} bytes")

    def send_packet(self, code, data=b""):
        if not (self.ser and self.ser.is_open):
            messagebox.showwarning("Port not open")
            return None
        pkt = (_build_with_payload(code, data)
               if data else _build_simple_packet(code))
        self.ser.reset_input_buffer()
        self.ser.write(pkt)
        self._log(">>> " + pkt.hex().upper())
        if DEBUG_MODE:
            return None
        buf = b""
        while True:
            c = self.ser.read(1)
            if not c:
                break
            buf += c
            if buf.endswith(bytes(FOOTER)):
                break
        if buf:
            self._log("<<< " + buf.hex().upper())
            return buf
        self._log("<<< timeout")
        return None

    def connect_device(self):
        self._log("Sending CONNECT")
        resp = self.send_packet(COMMAND_CODES['Connect'])
        if not resp:
            self._log("No response to CONNECT")
            return
        # enable on successful connect
        self.disconnect_btn.config(state="normal")
        for btn in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn):
            btn.config(state="normal")

        length = resp[4]
        payload = resp[5:5+length]
        vars_ = [self.bl_ver_var, self.fw_ver_var, self.pid_var, self.pver_var, self.appver_var]
        for i, var in enumerate(vars_):
            var.set(f"{payload[i]:02X}" if i < len(payload) else "N/A")

    def disconnect_device(self):
        self._log("Sending DISCONNECT")
        self.send_packet(COMMAND_CODES['Disconnect'])
        # disable operations
        self.disconnect_btn.config(state="disabled")
        for btn in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn):
            btn.config(state="disabled")

    def write_firmware(self):
        if not self.firmware_data:
            messagebox.showwarning("Load firmware first")
            return
        total = len(self.firmware_data)
        self._log(f"Writing {total} bytes in {MAX_CHUNK}-byte chunks")
        for off in range(0, total, MAX_CHUNK):
            chunk = self.firmware_data[off:off+MAX_CHUNK]
            self._log(f" → chunk @0x{off:06X}, {len(chunk)} bytes")
            self.send_packet(COMMAND_CODES['Write_FW'], chunk)
        self._log("Write complete")

    def read_firmware(self):
        self._log("Sending READ")
        self.send_packet(COMMAND_CODES['Read_FW'])

    def erase_firmware(self):
        self._log("Sending ERASE")
        self.send_packet(COMMAND_CODES['Erase_FW'])

    def reboot_mcu(self):
        self._log("Sending REBOOT")
        self.send_packet(COMMAND_CODES['Reboot'])

    def _log(self, txt):
        self.log.config(state="normal")
        self.log.insert("end", txt + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    root.columnconfigure(0, weight=1)
    root.rowconfigure(3, weight=1)
    root.rowconfigure(4, weight=1)
    BootloaderGUI(root)
    root.mainloop()
