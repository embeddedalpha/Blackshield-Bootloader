import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial
import serial.tools.list_ports

# ---------------------------------------------------------------------------------
# CRC configuration and calculator using the `crc` Python package.
# This computes CRC-32 over each byte expanded to 32-bit big-endian before CRC.
# ---------------------------------------------------------------------------------
from crc import Calculator, Configuration

# CRC configuration (32-bit, poly=0x04C11DB7, no reflection, no final XOR)
config = Configuration(
    width=32,
    polynomial=0x04C11DB7,
    init_value=0xFFFFFFFF,
    final_xor_value=0,
    reverse_input=False,
    reverse_output=False,
)
crc_calculator = Calculator(config)

HEADER_PREFIX = [0xAA, 0x55]
FOOTER_SUFFIX = [0xBB, 0x66]
REQUEST_BYTE  = 0x01

def _build_simple_packet(cmd_byte: int) -> bytes:
    """
    Build a packet of form:
      [0xAA, 0x55, cmd_byte, 0x01, CRC32, 0xBB, 0x66]
    CRC32 covers only: [cmd_byte, 0x01], each expanded to 32-bit big-endian word.
    """
    body = [cmd_byte, REQUEST_BYTE]
    # Convert each 8-bit byte into a 32-bit big-endian word before CRC
    to_crc = b''.join(b.to_bytes(4, 'big') for b in body)
    crc = crc_calculator.checksum(to_crc)
    pkt = bytearray(HEADER_PREFIX) \
          + bytearray(body) \
          + crc.to_bytes(4, 'big') \
          + bytearray(FOOTER_SUFFIX)
    return bytes(pkt)

def _build_packet_with_payload(cmd_byte: int, payload: bytearray) -> bytes:
    """
    Build a packet of form:
      [0xAA, 0x55, cmd_byte, 0x01, <payload bytes...>, CRC32, 0xBB, 0x66]
    CRC32 covers only: [cmd_byte, 0x01, <payload>], each byte expanded to 32-bit big-endian word.
    """
    body = [cmd_byte, REQUEST_BYTE] + list(payload)
    to_crc = b''.join(b.to_bytes(4, 'big') for b in body)
    crc = crc_calculator.checksum(to_crc)
    pkt = bytearray(HEADER_PREFIX) \
          + bytearray(body) \
          + crc.to_bytes(4, 'big') \
          + bytearray(FOOTER_SUFFIX)
    return bytes(pkt)


# ---------------------------------------------------------------------------------
# COMMAND_CODES: adjust these values to match your bootloader’s actual opcodes.
# ---------------------------------------------------------------------------------
COMMAND_CODES = {
    'Connect_Device':            0xA1,
    'Disconnect_Device':         0xA2,
    'Fetch_Info':                0xA3,
    'Write_Firmware':            0xA0,
    'Read_Firmware':             0xA1,
    'Erase_Firmware':            0xA2,
    'Get_Firmware_Version':      0xA3,
    'Get_Product_ID':            0xA4,
    'Get_Product_Version':       0xA5,
    'Read_Application_Version':  0xA6,
    'Reboot_MCU':                0xA7
}


class BootloaderGUI:
    def __init__(self, master):
        self.master = master
        master.title("STM32F407 Bootloader GUI")
        master.resizable(False, False)

        # Serial port object
        self.ser = None

        # Firmware data buffer (raw bytes from .bin)
        self.firmware_data = b""

        # -----------------------
        # Frame: Port selection
        # -----------------------
        port_frame = ttk.LabelFrame(master, text="Serial Port Configuration", padding=10)
        port_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ttk.Label(port_frame, text="COM Port:").grid(row=0, column=0, sticky="w")
        self.port_cb = ttk.Combobox(
            port_frame,
            values=self._get_serial_ports(),
            state="readonly",
            width=15
        )
        self.port_cb.grid(row=0, column=1, padx=(5, 20))
        self.port_cb.set("Select Port")

        ttk.Label(port_frame, text="Baud Rate:").grid(row=0, column=2, sticky="w")
        self.baud_cb = ttk.Combobox(
            port_frame,
            values=["9600", "19200", "38400", "57600", "115200", "256000"],
            state="readonly",
            width=12
        )
        self.baud_cb.grid(row=0, column=3, padx=(5, 20))
        self.baud_cb.set("115200")

        self.refresh_btn = ttk.Button(
            port_frame,
            text="Refresh Ports",
            width=20,
            command=self._refresh_ports
        )
        self.refresh_btn.grid(row=0, column=4, padx=5, pady=5)

        self.open_btn = ttk.Button(
            port_frame,
            text="Open Port",
            width=20,
            command=self.open_port
        )
        self.open_btn.grid(row=0, column=5, padx=5, pady=5)

        self.close_btn = ttk.Button(
            port_frame,
            text="Close Port",
            width=20,
            command=self.close_port,
            state="disabled"
        )
        self.close_btn.grid(row=0, column=6, padx=5, pady=5)

        # -----------------------
        # Frame: Device Configuration
        # -----------------------
        device_frame = ttk.LabelFrame(master, text="Device Configuration", padding=10)
        device_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

        self.connect_btn = ttk.Button(
            device_frame,
            text="Connect Device",
            width=20,
            command=self.connect_device,
            state="disabled"
        )
        self.connect_btn.grid(row=0, column=0, padx=5, pady=5)

        self.disconnect_btn = ttk.Button(
            device_frame,
            text="Disconnect Device",
            width=20,
            command=self.disconnect_device,
            state="disabled"
        )
        self.disconnect_btn.grid(row=0, column=1, padx=5, pady=5)

        self.fetch_info_btn = ttk.Button(
            device_frame,
            text="Fetch Info",
            width=20,
            command=self.fetch_info,
            state="disabled"
        )
        self.fetch_info_btn.grid(row=0, column=2, padx=5, pady=5)

        # Fields to display fetched info
        self.bootloader_version_var = tk.StringVar(value="N/A")
        self.firmware_version_var = tk.StringVar(value="N/A")
        self.product_id_var = tk.StringVar(value="N/A")
        self.product_version_var = tk.StringVar(value="N/A")
        self.app_version_var = tk.StringVar(value="N/A")

        # Bootloader Version
        ttk.Label(device_frame, text="Bootloader Version:").grid(
            row=1, column=0, sticky="e", padx=5, pady=(10, 5))
        self.bootloader_version_entry = ttk.Entry(
            device_frame,
            textvariable=self.bootloader_version_var,
            width=25,
            state="readonly"
        )
        self.bootloader_version_entry.grid(row=1, column=1, padx=5, pady=(10, 5))

        # Firmware Version
        ttk.Label(device_frame, text="Firmware Version:").grid(
            row=1, column=2, sticky="e", padx=5, pady=(10, 5))
        self.firmware_version_entry = ttk.Entry(
            device_frame,
            textvariable=self.firmware_version_var,
            width=25,
            state="readonly"
        )
        self.firmware_version_entry.grid(row=1, column=3, padx=5, pady=(10, 5))

        # Product ID
        ttk.Label(device_frame, text="Product ID:").grid(
            row=2, column=0, sticky="e", padx=5, pady=5)
        self.product_id_entry = ttk.Entry(
            device_frame,
            textvariable=self.product_id_var,
            width=25,
            state="readonly"
        )
        self.product_id_entry.grid(row=2, column=1, padx=5, pady=5)

        # Product Version
        ttk.Label(device_frame, text="Product Version:").grid(
            row=2, column=2, sticky="e", padx=5, pady=5)
        self.product_version_entry = ttk.Entry(
            device_frame,
            textvariable=self.product_version_var,
            width=25,
            state="readonly"
        )
        self.product_version_entry.grid(row=2, column=3, padx=5, pady=5)

        # Application Version
        ttk.Label(device_frame, text="App Version:").grid(
            row=3, column=0, sticky="e", padx=5, pady=(5, 10))
        self.app_version_entry = ttk.Entry(
            device_frame,
            textvariable=self.app_version_var,
            width=25,
            state="readonly"
        )
        self.app_version_entry.grid(row=3, column=1, padx=5, pady=(5, 10))

        # -----------------------
        # Frame: Bootloader ops
        # -----------------------
        ops_frame = ttk.LabelFrame(master, text="Bootloader Operations", padding=10)
        ops_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Browse button: load .bin into memory and display its contents in the log
        self.browse_btn = ttk.Button(
            ops_frame,
            text="Browse Firmware",
            width=20,
            command=self.browse_file
        )
        self.browse_btn.grid(row=0, column=0, padx=5, pady=5)

        # Align all operation buttons in a single row (row 1)
        self.write_fw_btn = ttk.Button(
            ops_frame,
            text="Write Firmware",
            width=20,
            command=self.write_firmware,
            state="disabled"
        )
        self.write_fw_btn.grid(row=1, column=0, padx=5, pady=5)

        self.read_fw_btn = ttk.Button(
            ops_frame,
            text="Read Firmware",
            width=20,
            command=self.read_firmware,
            state="disabled"
        )
        self.read_fw_btn.grid(row=1, column=1, padx=5, pady=5)

        self.erase_fw_btn = ttk.Button(
            ops_frame,
            text="Erase Firmware",
            width=20,
            command=self.erase_firmware,
            state="disabled"
        )
        self.erase_fw_btn.grid(row=1, column=2, padx=5, pady=5)

        self.reboot_btn = ttk.Button(
            ops_frame,
            text="Reboot MCU",
            width=20,
            command=self.reboot_mcu,
            state="disabled"
        )
        self.reboot_btn.grid(row=1, column=3, padx=5, pady=5)

        # -----------------------
        # Frame: Log area
        # -----------------------
        log_frame = ttk.LabelFrame(master, text="Log", padding=10)
        log_frame.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.log_text = tk.Text(log_frame, width=80, height=20, state="disabled", wrap="none")
        self.log_text.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log_text.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.log_text.configure(xscrollcommand=hsb.set)

        # Make log area expand if window is resized
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

    # -------------------------------------------------------------------------
    # Utility: list available COM ports
    # -------------------------------------------------------------------------
    def _get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def _refresh_ports(self):
        self.port_cb['values'] = self._get_serial_ports()
        self.append_log("Refreshed COM port list.")

    # -------------------------------------------------------------------------
    # Open / Close serial port
    # -------------------------------------------------------------------------
    def open_port(self):
        port_name = self.port_cb.get()
        baud_rate = self.baud_cb.get()

        if port_name == "" or port_name == "Select Port":
            messagebox.showwarning("Warning", "Please select a COM port first.")
            return

        try:
            self.ser = serial.Serial(
                port=port_name,
                baudrate=int(baud_rate),
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1  # 1 second read timeout
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open {port_name} at {baud_rate} bps:\n{e}")
            return

        self.append_log(f"Opened port {port_name} at {baud_rate} bps.")
        self.open_btn.config(state="disabled")
        self.close_btn.config(state="normal")

        # Enable Device Configuration buttons
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="normal")
        self.fetch_info_btn.config(state="normal")

        # Enable all Bootloader Operations buttons
        for btn in [
            self.write_fw_btn,
            self.read_fw_btn,
            self.erase_fw_btn,
            self.reboot_btn
        ]:
            btn.config(state="normal")

    def close_port(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.append_log("Closed serial port.")
        self.open_btn.config(state="normal")
        self.close_btn.config(state="disabled")

        # Disable Device Configuration buttons
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="disabled")
        self.fetch_info_btn.config(state="disabled")

        # Disable all Bootloader Operations buttons
        for btn in [
            self.write_fw_btn,
            self.read_fw_btn,
            self.erase_fw_btn,
            self.reboot_btn
        ]:
            btn.config(state="disabled")

    # -------------------------------------------------------------------------
    # Browse for firmware file and display its data in the log
    # -------------------------------------------------------------------------
    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Firmware File",
            filetypes=[("Binary Files", "*.bin"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "rb") as f:
                self.firmware_data = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file:\n{e}")
            return

        # Display raw binary data (as hex) in the log
        hex_data = self.firmware_data.hex().upper()
        self.append_log("=== Firmware Data (Hex) ===")
        # Break into 32-character chunks (16 bytes per line) for readability
        for i in range(0, len(hex_data), 32):
            self.append_log(hex_data[i:i+32])
        self.append_log("=== End Firmware Data ===")

    # -------------------------------------------------------------------------
    # Build/send a packet, read and log response
    # -------------------------------------------------------------------------
    def send_packet(self, command_code: int, data: bytes = b""):
        """
        Build the packet:
          0xAA 0x55 [cmd][0x01][data…][CRC32][0xBB 0x66]

        - Payload = everything after 0xAA 0x55 and before CRC and before 0xBB 0x66.
        - Compute CRC over Payload only, with each byte expanded to 32-bit big-endian.
        """
        if not (self.ser and self.ser.is_open):
            messagebox.showwarning("Warning", "Serial port is not open.")
            return None

        # Use _build_simple_packet if no data, else _build_packet_with_payload
        if data:
            packet = _build_packet_with_payload(command_code, bytearray(data))
        else:
            packet = _build_simple_packet(command_code)

        try:
            self.ser.reset_input_buffer()
            self.ser.write(packet)
            self.append_log(f">>> Sent: {packet.hex().upper()}")
        except Exception as e:
            self.append_log(f"ERROR sending packet: {e}")
            return None

        # Read response until footer 0xBB 0x66 or timeout
        try:
            response = self._read_response()
            if response:
                self.append_log(f"<<< Received: {response.hex().upper()}")
            else:
                self.append_log("<<< No response (timeout)")
            return response
        except Exception as e:
            self.append_log(f"ERROR reading response: {e}")
            return None

    def _read_response(self) -> bytes:
        """
        Read bytes until footer 0xBB 0x66 is detected or timeout.
        Returns full response including header, payload, CRC, and footer.
        """
        end_marker = b"\xBB\x66"
        buffer = b""
        while True:
            chunk = self.ser.read(1)
            if not chunk:
                # timeout or no data
                return buffer if buffer else None
            buffer += chunk
            if buffer.endswith(end_marker):
                return buffer

    # -------------------------------------------------------------------------
    # Button callbacks for each bootloader operation
    # -------------------------------------------------------------------------
    def connect_device(self):
        self.append_log("Connecting to device...")
        self.send_packet(COMMAND_CODES['Connect_Device'])

    def disconnect_device(self):
        self.append_log("Disconnecting device...")
        self.send_packet(COMMAND_CODES['Disconnect_Device'])

    def fetch_info(self):
        """
        Fetch in sequence:
          1) Bootloader Version (Fetch_Info)
          2) Firmware Version (Get_Firmware_Version)
          3) Product ID (Get_Product_ID)
          4) Product Version (Get_Product_Version)
          5) Application Version (Read_Application_Version)
        Each response payload is parsed and displayed in its field.
        """
        # 1) Bootloader Version
        resp = self.send_packet(COMMAND_CODES['Fetch_Info'])
        if resp:
            payload = resp[2:-6] if len(resp) >= 8 else b""
            try:
                text = payload.decode('ascii', errors='ignore').strip()
                self.bootloader_version_var.set(text if text else payload.hex().upper())
            except:
                self.bootloader_version_var.set(payload.hex().upper())
        else:
            self.bootloader_version_var.set("N/A")

        # 2) Firmware Version
        resp = self.send_packet(COMMAND_CODES['Get_Firmware_Version'])
        if resp:
            payload = resp[2:-6] if len(resp) >= 8 else b""
            try:
                text = payload.decode('ascii', errors='ignore').strip()
                self.firmware_version_var.set(text if text else payload.hex().upper())
            except:
                self.firmware_version_var.set(payload.hex().upper())
        else:
            self.firmware_version_var.set("N/A")

        # 3) Product ID
        resp = self.send_packet(COMMAND_CODES['Get_Product_ID'])
        if resp:
            payload = resp[2:-6] if len(resp) >= 8 else b""
            try:
                text = payload.decode('ascii', errors='ignore').strip()
                self.product_id_var.set(text if text else payload.hex().upper())
            except:
                self.product_id_var.set(payload.hex().upper())
        else:
            self.product_id_var.set("N/A")

        # 4) Product Version
        resp = self.send_packet(COMMAND_CODES['Get_Product_Version'])
        if resp:
            payload = resp[2:-6] if len(resp) >= 8 else b""
            try:
                text = payload.decode('ascii', errors='ignore').strip()
                self.product_version_var.set(text if text else payload.hex().upper())
            except:
                self.product_version_var.set(payload.hex().upper())
        else:
            self.product_version_var.set("N/A")

        # 5) Application Version
        resp = self.send_packet(COMMAND_CODES['Read_Application_Version'])
        if resp:
            payload = resp[2:-6] if len(resp) >= 8 else b""
            try:
                text = payload.decode('ascii', errors='ignore').strip()
                self.app_version_var.set(text if text else payload.hex().upper())
            except:
                self.app_version_var.set(payload.hex().upper())
        else:
            self.app_version_var.set("N/A")

    def write_firmware(self):
        if not self.firmware_data:
            messagebox.showwarning("Warning", "Please browse and load a firmware file first.")
            return

        self.append_log(f"Preparing to write firmware ({len(self.firmware_data)} bytes) …")
        self.send_packet(COMMAND_CODES['Write_Firmware'], self.firmware_data)

    def read_firmware(self):
        self.append_log("Reading firmware from device…")
        self.send_packet(COMMAND_CODES['Read_Firmware'])

    def erase_firmware(self):
        self.append_log("Erasing firmware…")
        self.send_packet(COMMAND_CODES['Erase_Firmware'])

    def reboot_mcu(self):
        self.append_log("Rebooting MCU…")
        self.send_packet(COMMAND_CODES['Reboot_MCU'])

    # -------------------------------------------------------------------------
    # Helper: append text to the log box
    # -------------------------------------------------------------------------
    def append_log(self, text: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = BootloaderGUI(root)
    root.mainloop()
