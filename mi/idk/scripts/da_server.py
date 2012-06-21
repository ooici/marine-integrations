__author__ = 'Bill French'

import argparse

from mi.idk.da_server import DirectAccessServer
from mi.idk.exceptions import ParameterRequired

def run():
    app = DirectAccessServer()
    opts = parseArgs()

    if(opts.telnet and opts.vps):
        ParameterRequired("-t and -v are mutually exclusive")

    if(opts.telnet):
        app.start_telnet_server()
    
    elif(opts.vps):
        app.start_vps_server()

    else:
        ParameterRequired("-t or -v required.")
    

def launch_logger_window():
    pass

def launch_stream_window():
    pass

def parseArgs():
    parser = argparse.ArgumentParser(description="IDK Start Direct Access")
    parser.add_argument("-t", dest='telnet', action="store_true",
                        help="run telnet direct access" )
    parser.add_argument("-v", dest='vps', action="store_true",
                        help="run virtual serial port access" )
    return parser.parse_args()


if __name__ == '__main__':
    run()
