import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError as exc:
    raise SystemExit(
        "customtkinter is required for this UI. Install it with: pip install customtkinter"
    ) from exc

import serial
import serial.tools.list_ports
from crc import Calculator, Configuration

DEBUG_MODE = False

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

CARD_FG = "#161B22"
CARD_BORDER = "#2B3240"
CARD_HEADER = "#10161F"
ACCENT = "#3B82F6"
ACCENT_HOVER = "#2563EB"
SUCCESS = "#16A34A"
WARNING = "#D97706"
DANGER = "#DC2626"
TEXT_MUTED = "#9CA3AF"
TEXT_PRIMARY = "#E5E7EB"
TEXTBOX_FG = "#0B1220"
PANEL_FG = "#101826"


def _crc_over_fields(fields) -> int:
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


class InfoField(ctk.CTkFrame):
    def __init__(self, master, label_text: str, variable: tk.StringVar, width: int = 112):
        super().__init__(master, fg_color="transparent")
        self.label = ctk.CTkLabel(
            self,
            text=label_text,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.entry = ctk.CTkEntry(
            self,
            width=width,
            textvariable=variable,
            state="readonly",
            fg_color=TEXTBOX_FG,
            border_color=CARD_BORDER,
            text_color=TEXT_PRIMARY,
            height=30,
        )
        self.entry.grid(row=0, column=1, sticky="w")


class BootloaderGUI(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.master = master
        self.master.title("Blackshield Bootloader" + (" [DEBUG]" if DEBUG_MODE else ""))
        self._configure_window(master)

        self.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=5)
        self.grid_rowconfigure(4, weight=3)

        self.ser = None
        self.firmware_data = b""
        self.readback_data = b""
        self.readback_reported_size = None
        self.readback_reported_crc = None
        self._offset = 0
        self._aborted = False

        self.bl_ver_var = tk.StringVar(value="N/A")
        self.fw_ver_var = tk.StringVar(value="N/A")
        self.pid_var = tk.StringVar(value="N/A")
        self.pver_var = tk.StringVar(value="N/A")
        self.appver_var = tk.StringVar(value="N/A")

        self._build_header()
        self._build_serial_card()
        self._build_control_card()
        self._build_hex_card()
        self._build_log_card()

    def _configure_window(self, master):
        screen_w = master.winfo_screenwidth()
        screen_h = master.winfo_screenheight()
        width = max(1280, int(screen_w * 0.95))
        height = max(840, int(screen_h * 0.92))
        master.geometry(f"{width}x{height}+0+0")
        master.minsize(1220, 780)
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Blackshield Bootloader",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w")
        # ctk.CTkLabel(
        #     header,
        #     text="Serial bootloader utility for connect, write, read, and validation.",
        #     font=ctk.CTkFont(size=12),
        #     text_color=TEXT_MUTED,
        # ).grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _make_card(self, row: int, title: str, subtitle: str | None = None, *, sticky: str = "ew"):
        card = ctk.CTkFrame(
            self,
            corner_radius=14,
            fg_color=CARD_FG,
            border_width=1,
            border_color=CARD_BORDER,
        )
        card.grid(row=row, column=0, sticky=sticky, pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(card, fg_color=CARD_HEADER, corner_radius=12)
        head.grid(row=0, column=0, sticky="ew", padx=1, pady=1)
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            head,
            text=title,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 0))
        if subtitle:
            ctk.CTkLabel(
                head,
                text=subtitle,
                font=ctk.CTkFont(size=11),
                text_color=TEXT_MUTED,
            ).grid(row=1, column=0, sticky="w", padx=14, pady=(3, 10))
        else:
            head.grid_rowconfigure(1, minsize=10)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=12)
        body.grid_columnconfigure(0, weight=1)
        return card, body

    def _build_serial_card(self):
        _, body = self._make_card(
            1,
            "Serial Port Configuration",
        )
        for c in range(7):
            body.grid_columnconfigure(c, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(body, text="COM Port", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=4
        )
        ports = self._list_ports()
        self.port_cb = ctk.CTkComboBox(body, values=ports or ["No Ports"], width=210, height=32)
        self.port_cb.grid(row=0, column=1, sticky="w", padx=(0, 18), pady=4)
        self.port_cb.set(ports[0] if ports else "Select Port")

        ctk.CTkLabel(body, text="Baud Rate", text_color=TEXT_MUTED, font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=4
        )
        self.baud_cb = ctk.CTkComboBox(
            body,
            values=["9600", "19200", "38400", "57600", "115200", "230400", "256000", "460800", "921600"],
            width=160,
            height=32,
        )
        self.baud_cb.grid(row=0, column=3, sticky="w", padx=(0, 18), pady=4)
        self.baud_cb.set("115200")

        self.refresh_btn = ctk.CTkButton(body, text="Refresh", width=110, height=32, command=self._refresh_ports, fg_color="#334155", hover_color="#475569")
        self.refresh_btn.grid(row=0, column=4, padx=4, pady=4)

        self.open_btn = ctk.CTkButton(body, text="Open Port", width=110, height=32, command=self.open_port, fg_color=ACCENT, hover_color=ACCENT_HOVER)
        self.open_btn.grid(row=0, column=5, padx=4, pady=4)

        self.close_btn = ctk.CTkButton(body, text="Close Port", width=110, height=32, command=self.close_port, state="disabled", fg_color="#1F2937", hover_color="#374151")
        self.close_btn.grid(row=0, column=6, padx=4, pady=4)

    def _build_control_card(self):
        _, body = self._make_card(
            2,
            "Device Configuration and Operations",
        )
        body.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.grid_columnconfigure(1, weight=1)

        button_row = ctk.CTkFrame(top, fg_color="transparent")
        button_row.grid(row=0, column=0, sticky="w")
        self.connect_btn = ctk.CTkButton(button_row, text="Connect", width=120, height=32, command=self.connect_device, state="disabled", fg_color=SUCCESS, hover_color="#15803D")
        self.connect_btn.grid(row=0, column=0, padx=(0, 10))
        self.disconnect_btn = ctk.CTkButton(button_row, text="Disconnect", width=120, height=32, command=self.disconnect_device, state="disabled", fg_color="#334155", hover_color="#475569")
        self.disconnect_btn.grid(row=0, column=1)

        info_row = ctk.CTkFrame(top, fg_color="transparent")
        info_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.info_fields = [
            InfoField(info_row, "Bootloader Version", self.bl_ver_var),
            InfoField(info_row, "Firmware Version", self.fw_ver_var),
            InfoField(info_row, "Product ID", self.pid_var),
            InfoField(info_row, "Product Version", self.pver_var),
            InfoField(info_row, "App Version", self.appver_var),
        ]
        for i, field in enumerate(self.info_fields):
            field.grid(row=0, column=i, sticky="w", padx=(0, 22), pady=2)

        ops = ctk.CTkFrame(body, fg_color=PANEL_FG, corner_radius=12, border_width=1, border_color=CARD_BORDER)
        ops.grid(row=1, column=0, sticky="ew")
        for c in range(7):
            ops.grid_columnconfigure(c, weight=0)

        ctk.CTkLabel(
            ops,
            text="Bootloader Operations",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=7, sticky="w", padx=12, pady=(10, 4))

        self.browse_btn = ctk.CTkButton(ops, text="Browse Firmware", width=150, height=34, command=self.browse_file, fg_color=ACCENT, hover_color=ACCENT_HOVER)
        self.browse_btn.grid(row=1, column=0, padx=(12, 6), pady=(6, 12), sticky="w")

        self.write_btn = ctk.CTkButton(ops, text="Write Firmware", width=145, height=34, command=self.write_firmware, state="disabled", fg_color="#1F2937", hover_color="#374151")
        self.read_btn = ctk.CTkButton(ops, text="Read Firmware", width=145, height=34, command=self.read_firmware, state="disabled", fg_color="#1F2937", hover_color="#374151")
        self.validate_btn = ctk.CTkButton(ops, text="Validate Firmware", width=145, height=34, command=self.validate_firmware, state="disabled", fg_color="#1F2937", hover_color="#374151")
        self.erase_btn = ctk.CTkButton(ops, text="Erase Firmware", width=145, height=34, command=self.erase_firmware, state="disabled", fg_color=WARNING, hover_color="#B45309")
        self.reboot_btn = ctk.CTkButton(ops, text="Reboot", width=145, height=34, command=self.reboot_mcu, state="disabled", fg_color=DANGER, hover_color="#B91C1C")

        self.write_btn.grid(row=1, column=1, padx=6, pady=(6, 12), sticky="w")
        self.read_btn.grid(row=1, column=2, padx=6, pady=(6, 12), sticky="w")
        self.validate_btn.grid(row=1, column=3, padx=6, pady=(6, 12), sticky="w")
        self.erase_btn.grid(row=1, column=4, padx=6, pady=(6, 12), sticky="w")
        self.reboot_btn.grid(row=1, column=5, padx=6, pady=(6, 12), sticky="w")

        if DEBUG_MODE:
            self.next_btn = ctk.CTkButton(ops, text="Next Chunk", width=145, height=34, command=self.send_next_chunk, state="disabled")
            self.abort_btn = ctk.CTkButton(ops, text="Abort Write", width=145, height=34, command=self.abort_write, state="disabled", fg_color=DANGER, hover_color="#B91C1C")
            self.next_btn.grid(row=1, column=6, padx=6, pady=(6, 12), sticky="w")
            self.abort_btn.grid(row=1, column=7, padx=(6, 12), pady=(6, 12), sticky="w")

    def _build_hex_card(self):
        _, body = self._make_card(
            3,
            "Firmware Hex View",
            sticky="nsew",
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, corner_radius=12, fg_color=PANEL_FG, border_width=1, border_color=CARD_BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(left, text="Selected Firmware (Write)", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.write_hex_box = ctk.CTkTextbox(left, fg_color=TEXTBOX_FG, border_width=1, border_color=CARD_BORDER, font=("Consolas", 12), activate_scrollbars=True, wrap="none")
        self.write_hex_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        right = ctk.CTkFrame(body, corner_radius=12, fg_color=PANEL_FG, border_width=1, border_color=CARD_BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(right, text="MCU Firmware (Read)", font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_PRIMARY).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 6)
        )
        self.read_hex_box = ctk.CTkTextbox(right, fg_color=TEXTBOX_FG, border_width=1, border_color=CARD_BORDER, font=("Consolas", 12), activate_scrollbars=True, wrap="none")
        self.read_hex_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self._set_textbox_content(self.write_hex_box, "No firmware selected.\n")
        self._set_textbox_content(self.read_hex_box, "No firmware read from MCU yet.\n")

    def _build_log_card(self):
        _, body = self._make_card(
            4,
            "Activity Log",
            "Protocol traffic, validation results, and error traces.",
            sticky="nsew",
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        self.log = ctk.CTkTextbox(
            body,
            fg_color=TEXTBOX_FG,
            border_width=1,
            border_color=CARD_BORDER,
            font=("Consolas", 12),
            activate_scrollbars=True,
            wrap="none",
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.configure(state="disabled")

    def _set_widget_state(self, widget, enabled: bool):
        widget.configure(state="normal" if enabled else "disabled")

    def _set_textbox_content(self, textbox: ctk.CTkTextbox, content: str):
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("1.0", content)
        textbox.configure(state="disabled")

    def _list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def _refresh_ports(self):
        ports = self._list_ports()
        self.port_cb.configure(values=ports or ["No Ports"])
        self.port_cb.set(ports[0] if ports else "Select Port")
        self._log("Ports refreshed")

    def _render_hex_view(self, textbox: ctk.CTkTextbox, data: bytes, empty_message: str):
        if not data:
            self._set_textbox_content(textbox, empty_message + "\n")
            return
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_bytes = " ".join(f"{b:02X}" for b in chunk)
            ascii_bytes = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            lines.append(f"{i:08X}  {hex_bytes:<47}  {ascii_bytes}")
        self._set_textbox_content(textbox, "\n".join(lines) + "\n")

    def _update_validate_button_state(self):
        serial_ready = self.ser is not None and self.ser.is_open and self.disconnect_btn.cget("state") == "normal"
        validate_ready = (
            serial_ready
            and bool(self.firmware_data)
            and bool(self.readback_data)
            and self.readback_reported_size is not None
            and self.readback_reported_crc is not None
        )
        self._set_widget_state(self.validate_btn, validate_ready)

    def _try_parse_read_complete_ack(self, resp):
        if resp["cmd"] != COMMAND_CODES["Read_FW"]:
            return None
        if resp["length"] < 8:
            return None
        payload = resp["payload"]
        app_size = int.from_bytes(payload[:4], "big")
        app_crc = int.from_bytes(payload[4:8], "big")
        return app_size, app_crc

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
                sync = (sync + c)[-len(header):]
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
        if port in ("", "Select Port", "No Ports"):
            messagebox.showwarning("Warning", "Please select a COM port first")
            return
        try:
            self.ser = serial.Serial(port, int(self.baud_cb.get()), timeout=1)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._log(f"Opened {port}")
        self._set_widget_state(self.open_btn, False)
        self._set_widget_state(self.close_btn, True)
        self._set_widget_state(self.connect_btn, True)
        self._update_validate_button_state()

    def close_port(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self._log("Port closed")
        self._set_widget_state(self.open_btn, True)
        self._set_widget_state(self.close_btn, False)
        self._set_widget_state(self.connect_btn, False)
        self._set_widget_state(self.disconnect_btn, False)
        for b in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn, self.validate_btn):
            self._set_widget_state(b, False)

    def browse_file(self):
        fn = filedialog.askopenfilename(title="Select .bin", filetypes=[("BIN", "*.bin")])
        if not fn:
            return
        with open(fn, "rb") as f:
            self.firmware_data = f.read()
        crc32 = _crc_over_fields(self.firmware_data)
        self._log(f"Selected firmware CRC32 = 0x{crc32:08X}")
        self._render_hex_view(self.write_hex_box, self.firmware_data, "No firmware selected.")
        self._log(f"Loaded {len(self.firmware_data)} bytes into WRITE view")
        self._set_widget_state(self.write_btn, True)
        self._update_validate_button_state()

    def connect_device(self):
        self._log("Sending CONNECT")
        resp = self.send_packet(COMMAND_CODES["Connect"])
        if not resp:
            self._log("No response to CONNECT")
            return
        payload = resp["payload"]
        self._set_widget_state(self.disconnect_btn, True)
        for b in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn):
            self._set_widget_state(b, True)
        self._update_validate_button_state()
        for i, var in enumerate([self.bl_ver_var, self.fw_ver_var, self.pid_var, self.pver_var, self.appver_var]):
            var.set(f"{payload[i]:02X}" if i < len(payload) else "N/A")

    def disconnect_device(self):
        self._log("Sending DISCONNECT")
        self.send_packet(COMMAND_CODES["Disconnect"])
        self._set_widget_state(self.disconnect_btn, False)
        for b in (self.write_btn, self.read_btn, self.erase_btn, self.reboot_btn, self.validate_btn):
            self._set_widget_state(b, False)

    def write_firmware(self):
        if not self.firmware_data:
            messagebox.showwarning("Warning", "Load firmware first")
            return
        self._offset = 0
        self._aborted = False
        total = len(self.firmware_data)
        self._log(f"Write Firmware started: total {total} bytes")
        if DEBUG_MODE:
            self._set_widget_state(self.next_btn, True)
            self._set_widget_state(self.abort_btn, True)
            self.send_next_chunk()
            self._set_widget_state(self.write_btn, False)
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
            self._set_widget_state(self.next_btn, False)
            self._set_widget_state(self.abort_btn, False)
        self._set_widget_state(self.write_btn, True)
        self._log("Write process complete" + (" (aborted)" if self._aborted else ""))

    def read_firmware(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showwarning("Warning", "Open the serial port first")
            return
        self.readback_data = b""
        self.readback_reported_size = None
        self.readback_reported_crc = None
        self._render_hex_view(self.read_hex_box, self.readback_data, "No firmware read from MCU yet.")
        self._update_validate_button_state()
        self._log("Sending READ request")
        if not self._send_only_packet(COMMAND_CODES["Read_FW"]):
            return
        total_read = 0
        packet_count = 0
        saw_end_of_data = False
        while True:
            resp = self._recv_packet(timeout=2.0)
            if not resp:
                if total_read == 0:
                    self._log("READ timeout: no firmware data received")
                    messagebox.showwarning("Read Firmware", "No firmware data received from MCU.")
                elif self.readback_reported_size is None or self.readback_reported_crc is None:
                    self._log("READ timeout before final completion ACK with size/CRC")
                else:
                    self._log("READ stream complete")
                break
            if resp["cmd"] != COMMAND_CODES["Read_FW"]:
                self._log(f"Ignoring unexpected packet cmd=0x{resp['cmd']:02X} during READ")
                continue
            if saw_end_of_data and resp["length"] >= 8:
                parsed = self._try_parse_read_complete_ack(resp)
                if parsed is not None:
                    app_size, app_crc = parsed
                    self.readback_reported_size = app_size
                    self.readback_reported_crc = app_crc
                    self._log(f"READ completion ACK: size={app_size} bytes, CRC=0x{app_crc:08X}")
                    break
            chunk = resp["payload"]
            chunk_len = resp["length"]
            if chunk_len == 0:
                saw_end_of_data = True
                self._log("READ data stream end marker received; waiting for completion ACK")
                continue
            packet_count += 1
            self.readback_data += chunk
            total_read += chunk_len
            self._render_hex_view(self.read_hex_box, self.readback_data, "No firmware read from MCU yet.")
            self.update_idletasks()
            self._log(f"Read chunk #{packet_count}: {chunk_len} bytes, total {total_read} bytes")
            if chunk_len < MAX_CHUNK:
                saw_end_of_data = True
                self._log("Final READ data chunk received; waiting for completion ACK")
        if self.readback_data:
            crc32 = _crc_over_fields(self.readback_data)
            self._log(f"Readback firmware CRC32 = 0x{crc32:08X}")
            self._log(f"READ complete: {len(self.readback_data)} bytes loaded into READ view")
        self._update_validate_button_state()

    def validate_firmware(self):
        if not self.firmware_data:
            messagebox.showwarning("Validate Firmware", "Load the firmware file first.")
            return
        if not self.readback_data:
            messagebox.showwarning("Validate Firmware", "Read the firmware back from the MCU first.")
            return
        if self.readback_reported_size is None or self.readback_reported_crc is None:
            messagebox.showwarning("Validate Firmware", "No final READ completion ACK with size/CRC has been captured yet.")
            return
        selected_size = len(self.firmware_data)
        readback_size = len(self.readback_data)
        selected_crc = _crc_over_fields(self.firmware_data)
        readback_crc = _crc_over_fields(self.readback_data)
        checks = [
            (
                "Firmware bytes",
                self.firmware_data == self.readback_data,
                f"selected file and MCU readback are {'identical' if self.firmware_data == self.readback_data else 'different'}",
            ),
            (
                "Firmware size",
                selected_size == readback_size == self.readback_reported_size,
                f"file={selected_size} bytes, readback={readback_size} bytes, MCU ACK={self.readback_reported_size} bytes",
            ),
            (
                "Firmware CRC",
                selected_crc == readback_crc == self.readback_reported_crc,
                f"file=0x{selected_crc:08X}, readback=0x{readback_crc:08X}, MCU ACK=0x{self.readback_reported_crc:08X}",
            ),
        ]
        self._log("=== Firmware Validation ===")
        for name, passed, detail in checks:
            self._log(f"{name}: {'PASS' if passed else 'FAIL'} — {detail}")
        all_pass = all(passed for _, passed, _ in checks)
        if all_pass:
            messagebox.showinfo(
                "Validate Firmware",
                "Validation PASSED. Firmware bytes, size, and CRC all match the MCU readback and final READ completion ACK.",
            )
        else:
            messagebox.showerror(
                "Validate Firmware",
                "Validation FAILED. Check the log for the exact mismatch in bytes, size, or CRC.",
            )

    def erase_firmware(self):
        self._log("Sending ERASE")
        self.send_packet(COMMAND_CODES["Erase_FW"])

    def reboot_mcu(self):
        self._log("Sending REBOOT")
        self.send_packet(COMMAND_CODES["Reboot"])

    def _log(self, txt):
        self.log.configure(state="normal")
        self.log.insert("end", txt + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    BootloaderGUI(root)
    root.mainloop()
