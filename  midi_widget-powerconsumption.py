import subprocess
import re
import mido
from mido import Message
import rumps
import threading
import os

def open_terminal_with_password_prompt():
    try:
        # Run the sudo command in the terminal to prompt for password
        subprocess.run(['sudo', '-v'], check=True)

        # Rest of your logic...

    except subprocess.CalledProcessError as e:
        print(f"Error running sudo in the terminal: {e}")

def translate_to_midi(value, min_value, max_value, midi_min, midi_max):
    value = max(min(value, max_value), min_value)
    return int((value - min_value) / (max_value - min_value) * (midi_max - midi_min) + midi_min)

class MidiApp(rumps.App):
    def __init__(self):
        super(MidiApp, self).__init__("MIDI Widget")
        self.menu = ["Start", "Stop"]
        self.running = False
        self.output_port_name = 'IAC Driver Bus 1'  # Replace with your actual MIDI output port
        self.output_port = mido.open_output(self.output_port_name)
        self.combined_power_item = rumps.MenuItem("Combined Power: N/A")
        self.menu.add(self.combined_power_item)
        self.timer = rumps.Timer(self.update_gui, 1)
        self.mutex = threading.Lock()

    def fetch_power_values(self):
        try:
            cmd = ["sudo", "powermetrics", "-n", "1", "--samplers", "cpu_power", "gpu_power", "ane_power"]
            output = subprocess.check_output(cmd, universal_newlines=True)
            return output
        except subprocess.CalledProcessError as e:
            print(f"Error running powermetrics with sudo: {e}")
            return None

    def update_gui(self, sender):
        output = self.fetch_power_values()
        if output is not None:
            # Extract individual power values for CPU, GPU, and ANE
            cpu_pattern = r'CPU Power:\s+(\d+)\s+mW'
            gpu_pattern = r'GPU Power:\s+(\d+)\s+mW'
            ane_pattern = r'ANE Power:\s+(\d+)\s+mW'

            cpu_match = re.search(cpu_pattern, output)
            gpu_match = re.search(gpu_pattern, output)
            ane_match = re.search(ane_pattern, output)

            if cpu_match and gpu_match and ane_match:
                cpu_power = int(cpu_match.group(1))
                gpu_power = int(gpu_match.group(1))
                ane_power = int(ane_match.group(1))

                # Calculate combined power
                combined_power = cpu_power + gpu_power + ane_power

                # Translate combined power to MIDI range
                combined_power_midi = translate_to_midi(combined_power, 0, 20000, 0, 127)

                # Update the taskbar menu item with the combined power value on the main thread
                with self.mutex:
                    self.combined_power_item.title = f"Combined Power: {combined_power} mW"

                # Send MIDI message independently of GUI updates
                self.send_midi(combined_power_midi)
            else:
                print("Failed to extract power values from powermetrics output.")

    def send_midi(self, velocity):
        # Send MIDI message
        note_on_message = Message('note_on', note=64, velocity=velocity)
        self.output_port.send(note_on_message)

    @rumps.clicked("Start")
    def start_midi(self, _):
        if not self.running:
            self.running = True
            self.timer.start()

    @rumps.clicked("Stop")
    def stop_midi(self, _):
        if self.running:
            self.running = False
            self.timer.stop()

if __name__ == '__main__':
    app = MidiApp()
    app.run()