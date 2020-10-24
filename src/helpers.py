import matplotlib.pyplot as plt
from subprocess import Popen
import socket
from threading import Thread
from typing import Dict, List
from src.senders import Sender

RECEIVER_FILE = "run_receiver.py"
AVERAGE_SEGMENT_SIZE = 80

def generate_mahimahi_command(mahimahi_settings: Dict) -> str:
    """return a string of mahimahi command

        Args:
            mahimahi_settings (Dict): delay, queue_szie, loss_directive(optional only), trace_file

        Returns:
            str: mahimahi command which can be run in bash
    """
    if mahimahi_settings.get('loss'):
        loss_directive = "mm-loss downlink %f" % mahimahi_settings.get('loss')
    else:
        loss_directive = ""
    return "mm-delay {delay} {loss_directive} mm-link traces/{trace_file} traces/{trace_file} --downlink-queue=droptail --downlink-queue-args=bytes={queue_size}".format(
      delay=mahimahi_settings['delay'],
      queue_size=mahimahi_settings['queue_size'],
      loss_directive=loss_directive,
      trace_file=mahimahi_settings['trace_file']
    )

def get_open_udp_port():# TODO? maybe need some knowledge of socket (unp)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

        
def print_performance(sender: Sender, num_seconds: int):
    print("Results for sender %d:" % sender.port)
    print("Total Acks: %d" % sender.strategy.total_acks)
    print("Num Duplicate Acks: %d" % sender.strategy.num_duplicate_acks)
    
    print("%% duplicate acks: %f" % ((float(sender.strategy.num_duplicate_acks * 100))/sender.strategy.total_acks))
    print("Throughput (bytes/s): %f" % (AVERAGE_SEGMENT_SIZE * (sender.strategy.ack_count/num_seconds)))
    print("Average RTT (ms): %f" % ((float(sum(sender.strategy.rtts))/len(sender.strategy.rtts)) * 1000))
    
    timestamps = [ ack[0] for ack in sender.strategy.times_of_acknowledgements]
    seq_nums = [ ack[1] for ack in sender.strategy.times_of_acknowledgements]

    plt.scatter(timestamps, seq_nums)
    plt.xlabel("Timestamps")
    plt.ylabel("Sequence Numbers")

    plt.show()
    
    plt.plot(sender.strategy.cwnds)
    plt.xlabel("Time")
    plt.ylabel("Congestion Window Size")
    plt.show()
    print("")
    
    if len(sender.strategy.slow_start_thresholds) > 0:
        plt.plot(sender.strategy.slow_start_thresholds)
        plt.xlabel("Time")
        plt.ylabel("Slow start threshold")
        plt.show()
    print("")
    
def run_with_mahi_settings(mahimahi_settings: Dict, seconds_to_run: int, senders: List):
    """run mahimahi command with Runtime and Senders given

    Args:
        mahimahi_settings (Dict): delay, queue_size, loss_directive, trace_file of mahimahi parse_args
        seconds_to_run (int): running duration time
        senders (List): instances of Sender of specific ports and some strategy
    """
    mahimahi_cmd = generate_mahimahi_command(mahimahi_settings)

    sender_ports = " ".join(["$MAHIMAHI_BASE %s" % sender.port for sender in senders])# TODO? what's MAHIMAHI_BASE
    
    cmd = "%s -- sh -c 'python %s %s'" % (mahimahi_cmd, RECEIVER_FILE, sender_ports) # TODO? RECEIVER_FILE here is run_receiver.py which could not be found
    receiver_process = Popen(cmd, shell=True) # TODO? Ppopen() and kill() usage
    for sender in senders:
        sender.handshake()
    threads = [Thread(target=sender.run, args=[seconds_to_run]) for sender in senders]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    
    for sender in senders:
        print_performance(sender, seconds_to_run)
    receiver_process.kill()
