import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import serial.tools.list_ports

# ---------------------------------------------------------------------------------
# DEBUG MODE
# Set to True to skip waiting for MCU responses (useful for UI layout/testing)
# ---------------------------------------------------------------------------------
DEBUG_MODE = False

# ---------------------------------------------------------------------------------
# CRC configuration and calculator using the `crc` Python package.
# This computes CRC-32 over each byte expanded to 32-bit big-endian before CRC.
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

HEADER_PREFIX   = [0xAA, 0x55]
FOOTER_SUFFIX   = [0xBB, 0x66]
REQUEST_BYTE    = 0x01
MAX_CHUNK_SIZE  = 0xFF  # maximum payload per packet

def _build_simple_packet(cmd_byte: int) -> bytes:
    length = 0
    body = [cmd_byte, REQUEST_BYTE, length]
    to_crc = b''.join(b.to_bytes(4, 'big') for b in body)
    crc = crc_calculator.checksum(to_crc)
    return (
        bytearray(HEADER_PREFIX) +
        bytearray(body) +
        crc.to_bytes(4, 'big') +
        bytearray(FOOTER_SUFFIX)
    )

def _build_packet_with_payload(cmd_byte: int, payload: bytes) -> bytes:
    length = len(payload) & 0xFF
    body = [cmd_byte, REQUEST_BYTE, length] + list(payload)
    to_crc = b''.join(b.to_bytes(4, 'big') for b in body)
    crc = crc_calculator.checksum(to_crc)
    return (
        bytearray(HEADER_PREFIX) +
        bytearray(body) +
        crc.to_bytes(4, 'big') +
        bytearray(FOOTER_SUFFIX)
    )

# ---------------------------------------------------------------------------------
# COMMAND_CODES: adjust these values to match your bootloader’s actual opcodes.
# ---------------------------------------------------------------------------------
COMMAND_CODES = {
    'Connect_Device':            0xA1,
    'Disconnect_Device':         0xA2,
    'Fetch_Info':                0xA3,
    'Write_Firmware':            0xA0,
    'Read_Firmware':             0xA4,
    'Erase_Firmware':            0xA5,
    'Get_Firmware_Version':      0xA6,
    'Get_Product_ID':            0xA7,
    'Get_Product_Version':       0xA8,
    'Read_Application_Version':  0xA9,
    'Reboot_MCU':                0xAA
}

class BootloaderGUI(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        master.title("STM32F407 Bootloader GUI" + (" [DEBUG]" if DEBUG_MODE else ""))
        master.resizable(False, False)
        self.grid(sticky="nsew")

        self.ser = None
        self.firmware_data = b""

        # Port selection
        port_frame = ttk.LabelFrame(self, text="Serial Port Configuration", padding=10)
        port_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        port_frame.columnconfigure(1, weight=1)

        ttk.Label(port_frame, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_cb = ttk.Combobox(port_frame, values=self._get_serial_ports(),
                                    state="readonly", width=15)
        self.port_cb.grid(row=0, column=1, padx=5, sticky="w")
        self.port_cb.set("Select Port")

        ttk.Label(port_frame, text="Baud Rate:").grid(row=0, column=2, sticky="w")
        self.baud_cb = ttk.Combobox(port_frame,
                                    values=["9600","19200","38400","57600","115200","256000"],
                                    state="readonly", width=12)
        self.baud_cb.grid(row=0, column=3, padx=5, sticky="w")
        self.baud_cb.set("115200")

        ttk.Button(port_frame, text="Refresh Ports", width=15,
                   command=self._refresh_ports).grid(row=0, column=4, padx=5)
        self.open_btn = ttk.Button(port_frame, text="Open Port", width=15,
                                   command=self.open_port)
        self.open_btn.grid(row=0, column=5, padx=5)
        self.close_btn = ttk.Button(port_frame, text="Close Port", width=15,
                                    command=self.close_port, state="disabled")
        self.close_btn.grid(row=0, column=6, padx=5)

        # Device configuration
        device_frame = ttk.LabelFrame(self, text="Device Configuration", padding=10)
        device_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        for i in range(3):
            device_frame.columnconfigure(i, weight=1)

        self.connect_btn = ttk.Button(device_frame, text="Connect", width=15,
                                      command=self.connect_device, state="disabled")
        self.connect_btn.grid(row=0, column=0, padx=5, pady=5)
        self.disconnect_btn = ttk.Button(device_frame, text="Disconnect", width=15,
                                         command=self.disconnect_device, state="disabled")
        self.disconnect_btn.grid(row=0, column=1, padx=5)
        self.fetch_info_btn = ttk.Button(device_frame, text="Fetch Info", width=15,
                                         command=self.fetch_info, state="disabled")
        self.fetch_info_btn.grid(row=0, column=2, padx=5)

        # Info fields
        self.bootloader_version_var = tk.StringVar(value="N/A")
        self.firmware_version_var   = tk.StringVar(value="N/A")
        self.product_id_var         = tk.StringVar(value="N/A")
        self.product_version_var    = tk.StringVar(value="N/A")
        self.app_version_var        = tk.StringVar(value="N/A")

        labels = [
            ("Bootloader Version:", self.bootloader_version_var),
            ("Firmware Version:",   self.firmware_version_var),
            ("Product ID:",         self.product_id_var),
            ("Product Version:",    self.product_version_var),
            ("App Version:",        self.app_version_var),
        ]
        for row, (text, var) in enumerate(labels, start=1):
            ttk.Label(device_frame, text=text).grid(row=row, column=0, sticky="e", padx=5)
            ttk.Entry(device_frame, textvariable=var,
                      width=20, state="readonly").grid(row=row, column=1, columnspan=2, sticky="w", padx=5)

        # Bootloader operations
        ops_frame = ttk.LabelFrame(self, text="Bootloader Operations", padding=10)
        ops_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        for i in range(4):
            ops_frame.columnconfigure(i, weight=1)

        ttk.Button(ops_frame, text="Browse Firmware", width=15,
                   command=self.browse_file).grid(row=0, column=0, padx=5, pady=5)
        self.write_fw_btn = ttk.Button(ops_frame, text="Write Firmware", width=15,
                                       command=self.write_firmware, state="disabled")
        self.write_fw_btn.grid(row=1, column=0, padx=5)
        self.read_fw_btn = ttk.Button(ops_frame, text="Read Firmware", width=15,
                                      command=self.read_firmware, state="disabled")
        self.read_fw_btn.grid(row=1, column=1, padx=5)
        self.erase_fw_btn = ttk.Button(ops_frame, text="Erase Firmware", width=15,
                                       command=self.erase_firmware, state="disabled")
        self.erase_fw_btn.grid(row=1, column=2, padx=5)
        self.reboot_btn = ttk.Button(ops_frame, text="Reboot MCU", width=15,
                                     command=self.reboot_mcu, state="disabled")
        self.reboot_btn.grid(row=1, column=3, padx=5)

        # Firmware Hex View
        hex_frame = ttk.LabelFrame(self, text="Firmware Hex View", padding=10)
        hex_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")
        cols = ["Address"] + [f"{n:X}" for n in range(16)]
        self.hex_tree = ttk.Treeview(hex_frame, columns=cols, show="headings", height=10)
        for c in cols:
            self.hex_tree.heading(c, text=c)
            self.hex_tree.column(c, width=60, anchor="center")
        self.hex_tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(hex_frame, orient="vertical", command=self.hex_tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.hex_tree.configure(yscrollcommand=vsb.set)
        hex_frame.rowconfigure(0, weight=1)
        hex_frame.columnconfigure(0, weight=1)

        # Log area
        log_frame = ttk.LabelFrame(self, text="Log", padding=10)
        log_frame.grid(row=4, column=0, padx=10, pady=(0,10), sticky="nsew")
        self.log_text = tk.Text(log_frame, width=80, height=10, state="disabled", wrap="none")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        vsb2 = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        vsb2.grid(row=0, column=1, sticky="ns")
        hsb2 = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log_text.xview)
        hsb2.grid(row=1, column=0, sticky="ew")
        self.log_text.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        # Layout weight
        master.columnconfigure(0, weight=1)
        master.rowconfigure(3, weight=1)
        master.rowconfigure(4, weight=1)

    def _get_serial_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def _refresh_ports(self):
        self.port_cb['values'] = self._get_serial_ports()
        self.append_log("Refreshed COM port list.")

    def open_port(self):
        port = self.port_cb.get()
        if port in ("", "Select Port"):
            messagebox.showwarning("Warning", "Please select a COM port first.")
            return
        try:
            self.ser = serial.Serial(port, int(self.baud_cb.get()), timeout=1)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open port:\n{e}")
            return
        self.append_log(f"Opened port {port}")
        self.open_btn.config(state="disabled")
        self.close_btn.config(state="normal")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="normal")
        self.fetch_info_btn.config(state="normal")
        for btn in (self.write_fw_btn, self.read_fw_btn, self.erase_fw_btn, self.reboot_btn):
            btn.config(state="normal")

    def close_port(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.append_log("Closed serial port.")
        self.open_btn.config(state="normal")
        self.close_btn.config(state="disabled")
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="disabled")
        self.fetch_info_btn.config(state="disabled")
        for btn in (self.write_fw_btn, self.read_fw_btn, self.erase_fw_btn, self.reboot_btn):
            btn.config(state="disabled")

    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Select Firmware File",
            filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                self.firmware_data = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file:\n{e}")
            return

        # Calculate full-binary CRC
        to_crc_full = b''.join(b.to_bytes(4, 'big') for b in self.firmware_data)
        full_crc = crc_calculator.checksum(to_crc_full)
        self.append_log(f"Full binary CRC32: 0x{full_crc:08X}")

        # Populate hex view
        self.hex_tree.delete(*self.hex_tree.get_children())
        data = self.firmware_data
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            row = [f"0x{i:08X}"] + [f"{b:02X}" for b in chunk]
            row += [""] * (17 - len(row))
            self.hex_tree.insert("", "end", values=row)

        self.append_log(f"Loaded firmware: {len(data)} bytes")

    def send_packet(self, code, data=b""):
        if not (self.ser and self.ser.is_open):
            messagebox.showwarning("Warning", "Serial port is not open.")
            return None

        packet = (_build_packet_with_payload(code, data)
                  if data else _build_simple_packet(code))
        try:
            self.ser.reset_input_buffer()
            self.ser.write(packet)
            self.append_log(f">>> Sent: {packet.hex().upper()}")
        except Exception as e:
            self.append_log(f"ERROR sending packet: {e}")
            return None

        if DEBUG_MODE:
            self.append_log("DEBUG_MODE: skipping MCU response.")
            return None

        try:
            resp = self._read_response()
            if resp:
                self.append_log(f"<<< Received: {resp.hex().upper()}")
            else:
                self.append_log("<<< No response (timeout)")
            return resp
        except Exception as e:
            self.append_log(f"ERROR reading response: {e}")
            return None

    def _read_response(self):
        end_marker = b"\xBB\x66"
        buf = b""
        while True:
            chunk = self.ser.read(1)
            if not chunk:
                return buf or None
            buf += chunk
            if buf.endswith(end_marker):
                return buf

    def connect_device(self):
        self.append_log("Connecting to device...")
        self.send_packet(COMMAND_CODES['Connect_Device'])

    def disconnect_device(self):
        self.append_log("Disconnecting device...")
        self.send_packet(COMMAND_CODES['Disconnect_Device'])

    def fetch_info(self):
        def get_field(cmd, var):
            resp = self.send_packet(cmd)
            if resp and len(resp) >= 6:
                payload = resp[2:-6]
                try:
                    text = payload.decode('ascii', errors='ignore').strip()
                except:
                    text = ""
                var.set(text or payload.hex().upper())
            else:
                var.set("N/A")

        get_field(COMMAND_CODES['Fetch_Info'],           self.bootloader_version_var)
        get_field(COMMAND_CODES['Get_Firmware_Version'], self.firmware_version_var)
        get_field(COMMAND_CODES['Get_Product_ID'],       self.product_id_var)
        get_field(COMMAND_CODES['Get_Product_Version'],  self.product_version_var)
        get_field(COMMAND_CODES['Read_Application_Version'], self.app_version_var)

    def write_firmware(self):
        if not self.firmware_data:
            messagebox.showwarning("Warning", "Please load a firmware file first.")
            return

        total = len(self.firmware_data)
        self.append_log(f"Writing firmware in chunks of {MAX_CHUNK_SIZE} bytes (total {total} bytes)...")

        for offset in range(0, total, MAX_CHUNK_SIZE):
            chunk = self.firmware_data[offset:offset + MAX_CHUNK_SIZE]
            self.append_log(f" → Chunk @0x{offset:08X}, size {len(chunk)}")
            self.send_packet(COMMAND_CODES['Write_Firmware'], chunk)

        self.append_log("Write firmware complete.")

    def read_firmware(self):
        self.append_log("Reading firmware from device...")
        self.send_packet(COMMAND_CODES['Read_Firmware'])

    def erase_firmware(self):
        self.append_log("Erasing firmware...")
        self.send_packet(COMMAND_CODES['Erase_Firmware'])

    def reboot_mcu(self):
        self.append_log("Rebooting MCU...")
        self.send_packet(COMMAND_CODES['Reboot_MCU'])

    def append_log(self, text: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    root.columnconfigure(0, weight=1)
    root.rowconfigure(3, weight=1)
    root.rowconfigure(4, weight=1)
    app = BootloaderGUI(root)
    root.mainloop()
