#!/usr/bin/env python

USAGE = """

GP- This has been modified to make it a generic raw socket connection, with <CR><LF>

This program allows direct user interaction with the RAS_PPS instrument via a socket.


USAGE:
    RAS_PPS_testing.py address port  # connect to instrument on address:port
    RAS_PPS_testing.py port          # connect to instrument on localhost:port

Example:
    RAS_PPS_testing.py 10.31.8.7 4002
    
To save output to screen and to a log file:

    RAS_PPS_testing.py 10.31.8.7 4002 | tee file.txt

It establishes a TCP connection with the provided service, starts a thread to
print all incoming data from the associated socket, and goes into a loop to
dispatch commands from the user.

The commands are:
    - an empty string --> sends a '\r\n' (<CR><LF>)
    - the command 'wake' sends 5 control-Cs that wake and enable the RAS and PPS
    - the command 'autoTemp' starts a query of the Temp probe, only when connected to the correct port (4002)
    - once autoTemp enabled, any key followed by enter will exit autosample mode
    - the command 'autoRAS' starts a 200 burn-in simulation of the RAS, only when connected to the correct port (4001)
    - once autoRAS enabled, any key followed by enter will exit autosample mode
    - the command 'autoPPS' starts a 200 burn-in simulation of the PPS, only when connected to the correct port (4003)
    - once autoPPS enabled, any key followed by enter will exit autosample mode
    - The letter 'q' --> quits the program
    - Any other non-empty string --> sends the string followed by a '\r\n' (<CR><LF>)


"""

__author__ = 'Giora Proskurowski modified original Carlos Rueda'
__license__ = 'Apache 2.0'

import sys
import socket
import os
import time
import select

from threading import Thread


class _Recv(Thread):
    """
    Thread to receive and print data.
    """

    def __init__(self, conn):
        Thread.__init__(self, name="_Recv")
        self._conn = conn
        self._last_line = ''
        self._new_line = ''
        self.setDaemon(True)

    def _update_lines(self, recv):
        if recv == '\n':
            self._last_line = self._new_line
            self._new_line = ''
            return True
        else:
            self._new_line += recv
            return False

    def run(self):
        print "### _Recv running."
        while True:
            recv = self._conn.recv(1)
            newline = self._update_lines(recv)
            os.write(sys.stdout.fileno(), recv)
            sys.stdout.flush()


class _Direct(object):
    """
    Main program.
    """

    def __init__(self, host, port):
        """
        Establishes the connection and starts the receiving thread.
        """
        print "### connecting to %s:%s" % (host, port)
        print "For automatic temperature polling (port 4002) enter autoTemp"
        print "For automatic RAS burn-in (port 4001) enter autoRAS"
        print "For automatic PPS burn-in (port 4003) enter autoPPS"
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((host, port))
        self._bt = _Recv(self._sock)
        self._bt.start()

    def run(self):
        #        """
        #         Dispatches user commands.
        #         """
        while True:

            cmd = sys.stdin.readline()

            cmd = cmd.strip()

            if cmd == "wake":
                self.wake()

            elif cmd == "^C":
                print "### sending '%s'" % cmd
                self.send_control('c')

            elif cmd == "q":
                print "### exiting"
                break

            elif cmd == "autoTemp":
                self.automatic_control_temp()

            elif cmd == "autoRAS":
                self.automatic_control_RAS()

            elif cmd == "autoPPS":
                self.automatic_control_PPS()

            elif cmd == "scan":
                self.scan_addresses()

            elif cmd == "reset":
                self.reset_all()

            else:
                print "### sending '%s'" % cmd
                self.send(cmd)
                self.send('\r\n')

        self.stop()

    def wake(self):
        print "### attempting to wake"
        self.send_control('c')
        time.sleep(1)
        self.send_control('c')
        time.sleep(1)
        self.send_control('c')
        time.sleep(1)
        self.send_control('c')
        time.sleep(1)
        self.send_control('c')
        print "### five ^C sent"
        return True

    def automatic_control_temp(self):
        """
        Sends temp probe queries repeatedly until any keyed sequence is entered
        """
        print "### Automatic temperature polling mode"
        print "### To exit: input any key followed by enter"
        # The following two while loops do the same thing, however the exit strategy of the the second one,
        # utilizing a timer, is cleaner than the first, which utilizes a  hard break (thanks to Eric McRae)

        second = 0
        while True:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                stopcmd = sys.stdin.readline()
                print "### exiting polling mode"
                break
            if second == 1:
                print "Timestamp:", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                self.send('$1RD')
            if second == 1.25:
                self.send('$2RD')
            if second == 1.50:
                self.send('$3RD')
            time.sleep(.25)
            second += .25
            if second == 60:  # loop counter, was set to 10, now set to minute data for burn-in
                second = 0  # reset second counter

    def automatic_control_RAS(self):
        """
        Simulates a 200-hr burn in of the RAS, by cycling through all 48 ports and using the pump
        as it is used during sampling
        """
        print "### 200 hr burn-in simulation of RAS started"
        print "### To exit: input any key followed by enter"

        # The following two while loops do the same thing, however the exit strategy of the the second one,
        # utilizing a timer, is cleaner than the first, which utilizes a  hard break (thanks to Eric McRae)
        second = 0
        RASport = 10
        while True:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                stopcmd = sys.stdin.readline()
                print "### exiting 200 hr burn-in"
                break
            if port == 25:
                print "### exiting 200 hr burn-in, 24 ports tested, half yearly duty cycle"
                break
            if second == 1:
                print "Timestamp:", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                self.wake()
            if second == 20:  # actual is ~7s
                self.send('HOME')
            if second == 60:  # actual is ~15s
                self.send('FORWARD 150 100 25')
            if second == 260:  # actual is ~100s
                self.send('PORT ' + str(RASport))
            if second == 300:  # actual is ~15s
                self.send('FORWARD 425 75 25')
            if second == 750:  # actual is ~350s
                self.send('HOME')
            if second == 800:  # actual is ~15s
                self.send('REVERSE 75 100 25')
            if second == 900:  # actual is ~50s
                self.send('SLEEP')
            time.sleep(1)
            second += 1
            if second == 30000:  # this is to get 24 samples in 200hrs, half yearly duty cycle
                second = 0  # reset second counter
                RASport += 1


    def automatic_control_PPS(self):
        """
        Simulates a 200-hr burn in of the PPS, by cycling through all 24 ports and using the pump
        as it is used during sampling
        """
        print "### 200 hr burn-in simulation of PPS started"
        print "### To exit: input any key followed by enter"

        # The following two while loops do the same thing, however the exit strategy of the the second one,
        # utilizing a timer, is cleaner than the first, which utilizes a  hard break (thanks to Eric McRae)
        second = 0
        PPSport = 6
        while True:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                stopcmd = sys.stdin.readline()
                print "### exiting 200 hr burn-in"
                break
            if port == 13:
                print "### exiting 200 hr burn-in, 12 ports tested, half yearly duty cycle"
                break
            if second == 1:
                print "Timestamp:", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
                self.wake()
            if second == 20:  # actual is ~7s
                self.send('HOME')
            if second == 60:  # actual is ~20s
                self.send('FORWARD 150 100 75')
            if second == 260:  # actual is ~100s
                self.send('PORT ' + str(PPSport))
            if second == 300:  # actual is ~15s
                self.send('FORWARD 4000 100 75')
            if second == 3500:  # actual is ~3000s
                self.send('HOME')
            if second == 3540:  # actual is ~15s
                self.send('REVERSE 75 100 75')
            if second == 3640:  # actual is ~60s
                self.send('SLEEP')
            time.sleep(1)
            second += 1
            if second == 60000:  # this is to get 12 samples in 200 hrs, half yearly duty cycle
                second = 0  # reset second counter
                PPSport += 1

    def scan_addresses(self):
        exclude = (0, 0x0D, 0x24, 0x23, 0x7B, 0x7D)
        # for i in range(0x0, 0x7F):
        for i in range(0x31, 0x39):
            if i in exclude:
                continue
            address = chr(i)
            print '0x%02x' % i
            command = str('$%sRS\r' % address)
            # command = str('$%sSUXXX\r' % address)
            self.send(command)
            print

    def reset_all(self):
        exclude = (0, 0x0D, 0x24, 0x23, 0x7B, 0x7D)
        # for i in range(0x0, 0x7F):
        for i in range(0x31, 0x39):
            if i in exclude:
                continue
            address = chr(i)
            print '0x%02x' % i
            # command = str('$%sRS\r' % address)
            unit = str('#%s' % address)
            old_send = self.send
            self.send(unit + 'RS')
            self.send(unit + 'WE')
            self.send(unit + 'SU%02X021482' % i)
            self.send(unit + 'RS')

    def reset(self):
        self.send('#1RS', True)
        self.send('#1WE', True)
        self.send('#1SU31021482', True)
        self.send('#1RS', True)
        time.sleep(0.2)

        self.send('#2RS', True)
        self.send('#2WE', True)
        self.send('#2SU32021482', True)
        self.send('#2RS', True)
        time.sleep(0.2)

        self.send('#3RS', True)
        self.send('#3WE', True)
        self.send('#3SU33021482', True)
        self.send('#3RS', True)

    def stop(self):
        self._sock.close()

    def send(self, cmd, echo=False):
        """
        Sends a string. Returns the number of bytes written.
        """
        time.sleep(0.1)
        cmd += '\r\n'
        if echo:
            print "### sending '%r'" % cmd
        c = os.write(self._sock.fileno(), cmd)
        time.sleep(0.2)
        return c

    def send_control(self, char):
        """
        Sends a control character.
        @param char must satisfy 'a' <= char.lower() <= 'z'
        """
        char = char.lower()
        assert 'a' <= char <= 'z'
        a = ord(char)
        a = a - ord('a') + 1
        return self.send(chr(a))


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print USAGE
        exit()

    if len(sys.argv) == 2:
        host = 'localhost'
        port = int(sys.argv[1])
    else:
        host = sys.argv[1]
        port = int(sys.argv[2])

    direct = _Direct(host, port)
    direct.run()

