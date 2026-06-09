"""
Multi-laser test script — turns on several lasers (473nm Cobolt and/or 635nm red)
at the same time at configured powers, holds until DELETE, then shuts down all.

Edit the LASERS list in main() to choose which boards to test.
Each laser is brought up / torn down in its own thread so they run in parallel.
"""

import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

import keyboard
from colorama import init, Fore, Style
from pycobolt import Cobolt06MLD
from red_laser_control import RedLaser
from laser_control import wait_for_key
from utils.board_registry import BoardRegistry

init()
exit_key = 'del'

DEFAULT_REGISTRY = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config', 'board_registry.json'))

# Colors cycled through for per-laser log prefixes
_LOG_COLORS = [Fore.CYAN, Fore.MAGENTA, Fore.BLUE, Fore.GREEN, Fore.YELLOW, Fore.RED]
_print_lock = threading.Lock()


def _tagged_print(tag, color, msg):
    with _print_lock:
        print(f"{color}[{tag}]{Style.RESET_ALL} {msg}")


class LaserHandle:
    """Wraps a single laser device with bring-up / shutdown logic."""

    def __init__(self, registry, board_name, laser_type, power_mw, color):
        self.registry = registry
        self.board_name = board_name
        self.laser_type = laser_type
        self.power_mw = power_mw
        self.color = color
        self.laser = None
        self.ready = False

    def log(self, msg):
        _tagged_print(self.board_name, self.color, msg)

    def bring_up(self):
        port = self.registry.find_board_port(self.board_name)
        self.log(f"resolved to {port}")

        if self.laser_type == '473':
            self.laser = Cobolt06MLD(port=port)
            self.laser.clear_fault()
            self.laser.constant_power(power=0)
            self.laser.turn_on()
            time.sleep(2)

            if "Waiting for key" in self.laser.get_state():
                self.log(Fore.BLUE + "waiting for key — toggle key on box to continue" + Style.RESET_ALL)
                if not wait_for_key(self.laser):
                    self.log(Fore.YELLOW + "key check interrupted" + Style.RESET_ALL)
                    return False

            self.laser.constant_power(power=self.power_mw)
        elif self.laser_type == 'red':
            baudrate = self.registry.get_baudrate(self.board_name)
            self.laser = RedLaser(port=port, baudrate=baudrate)
            self.laser.connect()
            self.laser.turn_on()
            time.sleep(0.5)
            self.laser.set_power(self.power_mw)
        else:
            raise ValueError(f"Unknown laser_type '{self.laser_type}' for {self.board_name}")

        self.ready = True
        self.log(Fore.GREEN + f"ON at {self.power_mw} mW" + Style.RESET_ALL)
        return True

    def shut_down(self):
        if not self.laser:
            return
        try:
            if self.laser_type == '473':
                self.laser.constant_power(power=0)
                self.laser.turn_off()
                self.laser.disconnect()
            else:
                self.laser.turn_off()
                time.sleep(0.5)
                self.laser.disconnect()
            self.log(Fore.GREEN + "OFF and disconnected" + Style.RESET_ALL)
        except Exception as e:
            self.log(Fore.RED + f"shutdown error: {e}" + Style.RESET_ALL)


def run_parallel(registry, laser_specs):
    """Bring up all lasers concurrently, hold until DELETE, then shut down all."""
    handles = [
        LaserHandle(registry, spec['board'], spec['type'], spec['power_mw'],
                    _LOG_COLORS[i % len(_LOG_COLORS)])
        for i, spec in enumerate(laser_specs)
    ]

    print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
    print(Fore.CYAN + f"MULTI-LASER TEST — {len(handles)} laser(s)" + Style.RESET_ALL)
    print(Fore.CYAN + "=" * 70 + Style.RESET_ALL)
    for h in handles:
        print(f"  {h.color}{h.board_name}{Style.RESET_ALL}  type={h.laser_type}  power={h.power_mw} mW")
    print(f"\n  Press {Fore.YELLOW}DELETE{Style.RESET_ALL} to turn all lasers off\n")

    try:
        with ThreadPoolExecutor(max_workers=len(handles)) as pool:
            futures = {pool.submit(h.bring_up): h for h in handles}
            for fut, h in futures.items():
                try:
                    fut.result()
                except Exception as e:
                    h.log(Fore.RED + f"bring-up failed: {e}" + Style.RESET_ALL)

        ready = [h for h in handles if h.ready]
        if not ready:
            print(Fore.RED + "\nNo lasers came up — aborting" + Style.RESET_ALL)
            return False

        print(Fore.GREEN + f"\n{len(ready)}/{len(handles)} laser(s) running — DELETE to stop\n" + Style.RESET_ALL)
        while not keyboard.is_pressed(exit_key):
            time.sleep(0.1)
        print(Fore.YELLOW + "\nDELETE pressed — shutting down all lasers" + Style.RESET_ALL)
        return True

    except KeyboardInterrupt:
        print(Fore.YELLOW + "\nInterrupted — shutting down all lasers" + Style.RESET_ALL)
        return False
    finally:
        with ThreadPoolExecutor(max_workers=max(len(handles), 1)) as pool:
            list(pool.map(lambda h: h.shut_down(), handles))


def main():
    # ===== CONFIGURATION — edit this list to choose which lasers to test =====
    # Each entry: board name from board_registry.json, type ('473' or 'red'), power in mW
    LASERS = [
        {'board': '473_laser_1',   'type': '473', 'power_mw': 10.0},
        {'board': '473_laser_2',   'type': '473', 'power_mw': 10.0},        # {'board': '635nm_laser_1', 'type': 'red', 'power_mw': 10.0},
    ]
    # =========================================================================

    registry = BoardRegistry(DEFAULT_REGISTRY)
    try:
        success = run_parallel(registry, LASERS)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(Fore.RED + f"\nTest failed: {e}" + Style.RESET_ALL)
        sys.exit(1)


if __name__ == "__main__":
    main()
