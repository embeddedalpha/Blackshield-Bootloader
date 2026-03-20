import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import serial
import serial.tools.list_ports
from crc import Calculator, Configuration

# ---------------------------------------------------------------------------------
# DEBUG MODE
# When True, show "Next Chunk" and "Abort Write"; manual stepping.
# When False, write_firmware automatically waits for each ACK before sending next chunk.
# ---------------------------------------------------------------------------------
DEBUG_MODE = False

# ---------------------------------------------------------------------------------
# CRC configuration (CRC-32, poly=0x04C11DB7, no reflection, no final XOR)
# ---------------------------------------------------------------------------------
config = Configuration(
    width=32,
    polynomial=0x04C11DB7,
    init_value=0xFFFFFFFF,
    final_xor_value=0,
    reverse_input=False,
    reverse_output=False,
)
crc_calculator = Calculator(config)

HEADER = [0xAA, 0x55]
FOOTER = [0xBB, 0x66]
REQ_BYTE = 0x01
MAX_CHUNK = 0xFF

COMMAND_CODES = {
    "Connect": 0xA0,
    "Disconnect": 0xA1,
    "Write_FW": 0xA3,
    "Read_FW": 0xA4,
    "Erase_FW": 0xA5,
    "Reboot": 0xA6,
    "Write_Complete": 0xA7,
}


def _crc_over_fields(fields) -> int:
    """
    Preserve the original packet/CRC scheme exactly:
    every body field byte is widened to 32-bit big-endian before CRC.
    """
    return crc_calculator.checksum(b"".join(int(b).to_bytes(4, "big") for b in fields))


def _build_simple_packet(cmd: int) -> bytes:
    body = [cmd, REQ_BYTE, 0]
    crc = _crc_over_fields(body)
    return bytes(HEADER + body) + crc.to_bytes(4, "big") + bytes(FOOTER)


def _build_with_payload(cmd: int, data: bytes) -> bytes:
    length = len(data) & 0xFF
    body = [cmd, REQ_BYTE, length] + list(data)
    crc = _crc_over_fields(body)
    return bytes(HEADER + body) + crc.to_bytes(4, "big") + bytes(FOOTER)


class BootloaderGUI(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        master.title("STM32F407 Bootloader GUI" + (" [DEBUG]" if DEBUG_MODE else ""))
        master.resizable(True, True)
        self._configure_window(master)
        self.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=3)
        self.rowconfigure(4, weight=2)

        self.ser = None
        self.firmware_data = b""          # selected file for WRITE
        self.readback_data = b""          # data streamed from MCU during READ
        self._offset = 0
        self._aborted = False

        # --- Serial Port Frame ---
        pf = ttk.LabelFrame(self, text="Serial Port Configuration", padding=10)
        pf.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        pf.columnconfigure(1, weight=1)
        pf.columnconfigure(3, weight=1)
        pf.columnconfigure(7, weight=1)

        ttk.Label(pf, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_cb = ttk.Combobox(pf, values=self._list_ports(), state="readonly", width=15)
        self.port_cb.grid(row=0, column=1, padx=5, sticky="w")
        self.port_cb.set("Select Port")

        ttk.Label(pf, text="Baud Rate:").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.baud_cb = ttk.Combobox(
            pf,
            values=["9600", "19220", "38400", "57600", "115200", "256000"],
            state="readonly",
            width=12,
        )
        self.baud_cb.grid(row=0, column=3, padx=5, sticky="w")
        self.baud_cb.set("115200")

        ttk.Button(pf, text="Refresh", command=self._refresh_ports).grid(row=0, column=4, padx=5)
        self.open_btn = ttk.Button(pf, text="Open Port", command=self.open_port)
        self.open_btn.grid(row=0, column=5, padx=5)
        self.close_btn = ttk.Button(pf, text="Close Port", command=self.close_port, state="disabled")
        self.close_btn.grid(row=0, column=6, padx=5)

        # --- Device Frame & Info ---
        df = ttk.LabelFrame(self, text="Device Configuration", padding=10)
        df.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        df.columnconfigure(0, weight=1)
        df.columnconfigure(1, weight=1)
        df.columnconfigure(2, weight=1)

        self.connect_btn = ttk.Button(df, text="Connect", command=self.connect_device, state="disabled")
        self.disconnect_btn = ttk.Button(df, text="Disconnect", command=self.disconnect_device, state="disabled")
        self.connect_btn.grid(row=0, column=0, padx=5, pady=5)
        self.disconnect_btn.grid(row=0, column=1, padx=5)

        self.bl_ver_var = tk.StringVar(value="N/A")
        self.fw_ver_var = tk.StringVar(value="N/A")
        self.pid_var = tk.StringVar(value="N/A")
        self.pver_var = tk.StringVar(value="N/A")
        self.appver_var = tk.StringVar(value="N/A")

        for i, (label, var) in enumerate(
            [
                ("Bootloader Ver:", self.bl_ver_var),
                ("Firmware Ver:", self.fw_ver_var),
                ("Product ID:", self.pid_var),
                ("Product Ver:", self.pver_var),
                ("App Ver:", self.appver_var),
            ],
            start=1,
        ):
            ttk.Label(df, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=2)
            ttk.Entry(df, textvariable=var, width=20, state="readonly").grid(
                row=i, column=1, sticky="w", padx=5, pady=2
            )

        # --- Bootloader Operations ---
        of = ttk.LabelFrame(self, text="Bootloader Operations", padding=10)
        of.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        of.columnconfigure(tuple(range(6)), weight=1)

        ttk.Button(of, text="Browse Firmware", command=self.browse_file).grid(row=0, column=0, padx=5, pady=5)
        self.write_btn = ttk.Button(of, text="Write FW", command=self.write_firmware, state="disabled")
        self.read_btn = ttk.Button(of, text="Read FW", command=self.read_firmware, state="disabled")
        self.erase_btn = ttk.Button(of, text="Erase FW", command=self.erase_firmware, state="disabled")
        self.reboot_btn = ttk.Button(of, text="Reboot", command=self.reboot_mcu, state="disabled")
        self.write_btn.grid(row=1, column=0, padx=5)
        self.read_btn.grid(row=1, column=1, padx=5)
        self.erase_btn.grid(row=1, column=2, padx=5)
        self.reboot_btn.grid(row=1, column=3, padx=5)

        if DEBUG_MODE:
            self.next_btn = ttk.Button(of, text="Next Chunk", command=self.send_next_chunk, state="disabled")
            self.abort_btn = ttk.Button(of, text="Abort Write", command=self.abort_write, state="disabled")
            self.next_btn.grid(row=1, column=4, padx=5)
            self.abort_btn.grid(row=1, column=5, padx=5)

        # --- Dual Hex View Frame ---
        hf = ttk.LabelFrame(self, text="Firmware Hex View", padding=10)
        hf.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        hf.columnconfigure(0, weight=1)
        hf.columnconfigure(1, weight=1)
        hf.rowconfigure(0, weight=1)

        left_hf = ttk.LabelFrame(hf, text="Selected Firmware (Write)", padding=5)
        left_hf.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_hf.rowconfigure(0, weight=1)
        left_hf.columnconfigure(0, weight=1)

        right_hf = ttk.LabelFrame(hf, text="MCU Firmware (Read)", padding=5)
        right_hf.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_hf.rowconfigure(0, weight=1)
        right_hf.columnconfigure(0, weight=1)

        self.write_hex_tree = self._create_hex_tree(left_hf)
        self.read_hex_tree = self._create_hex_tree(right_hf)

        # --- Log Frame ---
        lf = ttk.LabelFrame(self, text="Log", padding=10)
        lf.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.log = tk.Text(lf, width=80, height=8, state="disabled", wrap="none")
        self.log.grid(row=0, column=0, sticky="nsew")
        sb2 = ttk.Scrollbar(lf, orient="vertical", command=self.log.yview)
        sb2.grid(row=0, column=1, sticky="ns")
        sb3 = ttk.Scrollbar(lf, orient="horizontal", command=self.log.xview)
        sb3.grid(row=1, column=0, sticky="ew")
        self.log.configure(yscrollcommand=sb2.set, xscrollcommand=sb3.set)
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)

        master.columnconfigure(0, weight=1)
        for row in range(5):
            master.rowconfigure(row, weight=0)
        master.rowconfigure(3, weight=3)
        master.rowconfigure(4, weight=2)

    def _configure_window(self, master):
        screen_w = master.winfo_screenwidth()
        screen_h = master.winfo_screenheight()
        width = max(1100, int(screen_w * 0.95))
        height = max(750, int(screen_h * 0.90))
        master.geometry(f"{width}x{height}+0+0")
        master.minsize(1100, 750)

    def _create_hex_tree(self, parent):
        cols = ["Addr"] + [f"{n:X}" for n in range(16)]
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=8)
        for c in cols:
            tree.heading(c, text=c)
            if c == "Addr":
                tree.column(c, width=90, minwidth=80, anchor="center", stretch=False)
            else:
                tree.column(c, width=42, minwidth=36, anchor="center", stretch=True)
        tree.grid(row=0, column=0, sticky="nsew")
        sbv = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        sbv.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=sbv.set)
        return tree

    def _list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def _refresh_ports(self):
        self.port_cb["values"] = self._list_ports()
        self._log("Ports refreshed")

    def _render_hex_view(self, tree, data: bytes):
        tree.delete(*tree.get_children())
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            row = [f"{i:08X}"] + [f"{b:02X}" for b in chunk]
            row += [""] * (17 - len(row))
            tree.insert("", "end", values=row)

    def _send_only_packet(self, code, data=b""):
        if not self.ser or not self.ser.is_open:
            self._log("Serial port is not open")
            return False
        pkt = _build_with_payload(code, data) if data else _build_simple_packet(code)
        self.ser.reset_input_buffer()
        self.ser.write(pkt)
        self._log(">>> " + pkt.hex().upper())
        return True

    def _recv_packet(self, timeout=None):
        if not self.ser or not self.ser.is_open:
            self._log("Serial port is not open")
            return None

        header = bytes(HEADER)
        footer = bytes(FOOTER)
        previous_timeout = self.ser.timeout
        if timeout is not None:
            self.ser.timeout = timeout

        try:
            sync = b""
            while True:
                c = self.ser.read(1)
                if not c:
                    return None
                sync = (sync + c)[-len(header) :]
                if sync == header:
                    break

            fixed = self.ser.read(3)
            if len(fixed) != 3:
                self._log("RX packet truncated before body header")
                return None

            cmd, req, length = fixed[0], fixed[1], fixed[2]
            payload = self.ser.read(length)
            if len(payload) != length:
                self._log("RX payload truncated")
                return None

            crc_bytes = self.ser.read(4)
            if len(crc_bytes) != 4:
                self._log("RX CRC truncated")
                return None

            footer_bytes = self.ser.read(2)
            if len(footer_bytes) != 2:
                self._log("RX footer truncated")
                return None
            if footer_bytes != footer:
                self._log(f"RX footer mismatch: got {footer_bytes.hex().upper()}")
                return None

            crc_rx = int.from_bytes(crc_bytes, "big")
            body = [cmd, req, length] + list(payload)
            crc_calc = _crc_over_fields(body)
            if crc_rx != crc_calc:
                self._log(f"RX CRC mismatch: got 0x{crc_rx:08X}, calc 0x{crc_calc:08X}")
                return None

            raw = header + fixed + payload + crc_bytes + footer_bytes
            self._log("<<< " + raw.hex().upper())
            return {
                "cmd": cmd,
                "req": req,
                "length": length,
                "payload": payload,
                "crc": crc_rx,
                "raw": raw,
            }
        finally:
            if timeout is not None and self.ser:
                self.ser.timeout = previous_timeout

    def send_packet(self, code, data=b"", timeout=None):
        if not self._send_only_packet(code, data):
            return None
        resp = self._recv_packet(timeout=timeout)
        if not resp:
            self._log("<<< timeout")
        return resp

    def open_port(self):
        port = self.port_cb.get()
        if port in ("", "Select Port"):
            messagebox.showwarning("Warning", "Please select a COM port first")
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
        for b in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn):
            b.config(state="disabled")

    def browse_file(self):
        fn = filedialog.askopenfilename(title="Select .bin", filetypes=[("BIN", "*.bin")])
        if not fn:
            return
        with open(fn, "rb") as f:
            self.firmware_data = f.read()

        crc32 = _crc_over_fields(self.firmware_data)
        self._log(f"Selected firmware CRC32 = 0x{crc32:08X}")
        self._render_hex_view(self.write_hex_tree, self.firmware_data)
        self._log(f"Loaded {len(self.firmware_data)} bytes into WRITE view")
        self.write_btn.config(state="normal")

    def connect_device(self):
        self._log("Sending CONNECT")
        resp = self.send_packet(COMMAND_CODES["Connect"])
        if not resp:
            self._log("No response to CONNECT")
            return

        payload = resp["payload"]
        self.disconnect_btn.config(state="normal")
        for b in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn):
            b.config(state="normal")

        for i, var in enumerate(
            [self.bl_ver_var, self.fw_ver_var, self.pid_var, self.pver_var, self.appver_var]
        ):
            var.set(f"{payload[i]:02X}" if i < len(payload) else "N/A")

    def disconnect_device(self):
        self._log("Sending DISCONNECT")
        self.send_packet(COMMAND_CODES["Disconnect"])
        self.disconnect_btn.config(state="disabled")
        for b in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn):
            b.config(state="disabled")

    def write_firmware(self):
        if not self.firmware_data:
            messagebox.showwarning("Warning", "Load firmware first")
            return

        self._offset = 0
        self._aborted = False
        total = len(self.firmware_data)
        self._log(f"Write FW started: total {total} bytes")

        if DEBUG_MODE:
            self.next_btn.config(state="normal")
            self.abort_btn.config(state="normal")
            self.send_next_chunk()
            self.write_btn.config(state="disabled")
        else:
            while self._offset < total:
                chunk = self.firmware_data[self._offset : self._offset + MAX_CHUNK]
                self._log(f"Sending chunk @0x{self._offset:06X}, {len(chunk)} bytes")
                resp = self.send_packet(COMMAND_CODES["Write_FW"], chunk)
                if not resp:
                    self._log("No ACK — aborting")
                    messagebox.showerror("Error", "No acknowledgement; aborting.")
                    return
                self._offset += len(chunk)
                self._log(f"Bytes sent: {self._offset}/{total}")

            size_bytes = total.to_bytes(4, "big")
            crc_full = _crc_over_fields(self.firmware_data)
            crc_bytes = crc_full.to_bytes(4, "big")
            self._log("Sending Write_Complete packet")
            self.send_packet(COMMAND_CODES["Write_Complete"], size_bytes + crc_bytes)
            self._log("Firmware write complete")

    def send_next_chunk(self):
        if self._aborted:
            return

        total = len(self.firmware_data)
        if self._offset >= total:
            self._finish_write()
            return

        chunk = self.firmware_data[self._offset : self._offset + MAX_CHUNK]
        self._log(f"Sending chunk @0x{self._offset:06X}, {len(chunk)} bytes")
        resp = self.send_packet(COMMAND_CODES["Write_FW"], chunk)
        if resp:
            self._offset += len(chunk)
            self._log(f"Bytes sent: {self._offset}/{total}")
            if self._offset >= total:
                size_bytes = total.to_bytes(4, "big")
                crc_full = _crc_over_fields(self.firmware_data)
                crc_bytes = crc_full.to_bytes(4, "big")
                self._log("Sending Write_Complete packet")
                self.send_packet(COMMAND_CODES["Write_Complete"], size_bytes + crc_bytes)
                self._finish_write()
        else:
            self._log("No ACK — waiting or abort")

    def abort_write(self):
        self._aborted = True
        self._log("Write aborted by user")
        self._finish_write()

    def _finish_write(self):
        if DEBUG_MODE:
            self.next_btn.config(state="disabled")
            self.abort_btn.config(state="disabled")
        self.write_btn.config(state="normal")
        self._log("Write process complete" + (" (aborted)" if self._aborted else ""))

    def read_firmware(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("Warning", "Open the serial port first")
            return

        self.readback_data = b""
        self._render_hex_view(self.read_hex_tree, self.readback_data)

        self._log("Sending READ request")
        if not self._send_only_packet(COMMAND_CODES["Read_FW"]):
            return

        total_read = 0
        packet_count = 0

        while True:
            resp = self._recv_packet(timeout=2.0)
            if not resp:
                if total_read == 0:
                    self._log("READ timeout: no firmware data received")
                    messagebox.showwarning("Read FW", "No firmware data received from MCU.")
                else:
                    self._log("READ timeout: assuming end of stream")
                break

            if resp["cmd"] != COMMAND_CODES["Read_FW"]:
                self._log(f"Ignoring unexpected packet cmd=0x{resp['cmd']:02X} during READ")
                continue

            chunk = resp["payload"]
            chunk_len = resp["length"]
            packet_count += 1

            if chunk_len == 0:
                self._log("READ end packet received (zero-length payload)")
                break

            self.readback_data += chunk
            total_read += chunk_len
            self._render_hex_view(self.read_hex_tree, self.readback_data)
            self.update_idletasks()
            self._log(f"Read chunk #{packet_count}: {chunk_len} bytes, total {total_read} bytes")

            if chunk_len < MAX_CHUNK:
                self._log("Final READ chunk received (short packet)")
                break

        if self.readback_data:
            crc32 = _crc_over_fields(self.readback_data)
            self._log(f"Readback firmware CRC32 = 0x{crc32:08X}")
            self._log(f"READ complete: {len(self.readback_data)} bytes loaded into READ view")

    def erase_firmware(self):
        self._log("Sending ERASE")
        self.send_packet(COMMAND_CODES["Erase_FW"])

    def reboot_mcu(self):
        self._log("Sending REBOOT")
        self.send_packet(COMMAND_CODES["Reboot"])

    def _log(self, txt):
        self.log.config(state="normal")
        self.log.insert("end", txt + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    root.columnconfigure(0, weight=1)
    BootloaderGUI(root)
    root.mainloop()
