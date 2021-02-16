import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import numpy as np
import sys
import time
import os
import ast
import math

from datetime import datetime
from collections import defaultdict

fontsize = "12"
params = {
    'figure.autolayout': True,
    'legend.fontsize': fontsize,
    'figure.figsize': (8, 8),
    'axes.labelsize': fontsize,
    'axes.titlesize': fontsize,
    'xtick.labelsize': fontsize,
    'ytick.labelsize': fontsize
}
plt.rcParams.update(params)


# Gets received sequence numbers and their time
def get_seq_nos(experiment_log):
    seq_no_times = []
    seq_no_values = []
    start_string = experiment_log[6].split()[1]
    end_string   = experiment_log[-3].split()[1]
    start = datetime.strptime(start_string, "%H:%M:%S.%f")
    end   = datetime.strptime(end_string, "%H:%M:%S.%f")
    for line in experiment_log[1:-3]:
        if line[0] == '\t':
            continue
        _, time_string, src, direction, dst, size, seq_num = line.split()
        # if receiving
        if direction == "->":
            time = datetime.strptime(time_string, "%H:%M:%S.%f")
            elapsed = (time - start).total_seconds()
            seq_no_times.append(elapsed)
            seq_no_values.append(int(seq_num))
    seconds = math.ceil((end - start).total_seconds())
    duration = math.ceil((end - start).total_seconds())
    return start, duration, (seq_no_times, seq_no_values)


# Get moves (locators and timestamps) from mobile node network
def get_moves(start, network_log):
    moves = []
    for line in network_log[1:]:
        if "Moving from" in line:
            _, time_string, _, _, from_locs, _, to_locs = line.split()
            from_loc = ast.literal_eval(from_locs)[0]
            to_loc = ast.literal_eval(to_locs)[0]
            time = datetime.strptime(time_string, "%H:%M:%S.%f")
            elapsed = (time - start).total_seconds()
            moves.append((from_loc, elapsed))
    return moves





def get_locator_packets(experiment_log, start):
    locator_packets = defaultdict(list)
    for line in experiment_log[1:-3]:
        if line[0] == '\t':
            continue
        _, time_string, remote_addrinfo, direction, local_addrinfo, size, seq_num = line.split()
        time = datetime.strptime(time_string, "%H:%M:%S.%f")
        elapsed = (time - start).total_seconds()
        size=int(size)
        
        if direction == "->":
            locator = ":".join(remote_addrinfo[1:].split("/")[1].split(":")[:4])
        else:
            locator = ":".join(local_addrinfo[1:].split("/")[1].split(":")[:4])
        locator_packets[locator].append((elapsed, size))
    return locator_packets


def get_locator_throughuts(locator_packets, end):
    locator_throughputs = {}
    for locator, packets in locator_packets.items():
        throughputs = []
        for i in range(0, end, throughput_window_tick):
            window = 0
            for elapsed, size in packets:
                if (elapsed > i - throughput_window_size / 2 and
                    elapsed < i + throughput_window_size / 2):
                    window += size
            throughputs.append(window / throughput_window_tick)
        locator_throughputs[locator] = throughputs
    throughputs = locator_throughputs.values()
    aggregate_throughput = []
    for i in range(0, int(end / throughput_window_tick)):
        aggregate_tick=sum(throughput[i] for throughput in throughputs)
        aggregate_throughput.append(aggregate_tick)
    locator_throughputs["aggregate"] = aggregate_throughput
    return locator_throughputs


def plot_seq_nos(node, seq_nos, moves, duration):
    seq_no_times, seq_no_values = seq_nos
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.grid(color='lightgray', linestyle='-', linewidth=1)
    ax.set_axisbelow(True)
    # ax.set_xlim(0, seq_no_times[-1])
    # ax.set_ylim(0, seq_no_values[-1])
    # ax.set_xlim(left=0)
    # ax.set_ylim(bottom=0)
    title="Received sequence numbers vs Time on %s" % node
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Sequence Number")
    # loc = plticker.MultipleLocator()
    # ax.xaxis.set_major_locator(loc)
    # ax.set_xticks(np.arange(0, seconds, step=seconds/10)) 
    # ax.set_yticks(np.arange(0, seq_nums[-1], step=seq_nums[-1]/10))
    # ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%0.1f'))
    # ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%0.1f'))
    ax.plot(np.array(seq_no_times), np.array(seq_no_values))
    ax.set_xlim(left=0, right=duration)
    ax.set_ylim(bottom=0)
    prev=0
    for from_loc, elapsed in moves:
        if elapsed > seq_no_times[-1]:
            break
        ax.axvline(x=elapsed, color='gray', linestyle='--')
        pos=elapsed-(elapsed-prev)/2
        ax.text(pos,seq_no_values[-1]/2,from_loc,color='gray',rotation=0,ha="center")
        prev=elapsed
    fig.savefig(os.path.join(out_dir, '%s.png' % title))


def plot_throughputs(locator_throughputs, duration, node):
    seconds_range = [i for i in range(0, duration, throughput_window_tick)]
    # max_throughout = max([max(throughput) for throughput in locator_throughputs.values()])
    for locator, throughputs in locator_throughputs.items():
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.grid(color='lightgray', linestyle='-', linewidth=1)
        ax.set_axisbelow(True)
        title="%ds Moving average throughput vs Time on %s %s" % (throughput_window_size, node, locator)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Throughput (B/s)")
        
        # ax.set_xticks(np.arange(0, duration, step=60)) 
        # # ax.set_yticks(np.arange(0, max_throughout, step=1000))

        ax.plot(np.array(seconds_range), np.array(throughputs), label=locator)
        ax.set_xlim(left=0, right=duration)
        # ax.set_ylim(bottom=0, top=max_throughout)
        ax.set_ylim(bottom=0)
    
        ax.legend()

        fig.savefig(os.path.join(out_dir, '%s.png' % title))


if __name__ == "__main__":
    log_dir = sys.argv[1]
    global out_dir
    out_dir = log_dir

    global throughput_window_size
    global throughput_window_tick
    throughput_window_size = 1
    throughput_window_tick = 1

    alice_experiment_log = open(os.path.join(log_dir, "experiment_alice.log"), "r").readlines()
    alice_network_log    = open(os.path.join(log_dir, "network_alice.log"   ), "r").readlines()
    bob_experiment_log   = open(os.path.join(log_dir, "experiment_bob.log"  ), "r").readlines()
    bob_network_log      = open(os.path.join(log_dir, "network_bob.log"     ), "r").readlines()
    

    alice_start, alice_duration, alice_seq_nos = get_seq_nos(alice_experiment_log)
    alice_moves = get_moves(alice_start, alice_network_log)
    if alice_seq_nos != ([], []):
        plot_seq_nos("MN", alice_seq_nos, alice_moves, alice_duration)

    alice_locator_packets = get_locator_packets(alice_experiment_log, alice_start)
    alice_locator_throughputs = get_locator_throughuts(alice_locator_packets, alice_duration)
    plot_throughputs(alice_locator_throughputs, alice_duration, "MN")


    bob_start, bob_duration, bob_seq_nos = get_seq_nos(bob_experiment_log)
    if bob_seq_nos != ([], []):
        plot_seq_nos("CN", bob_seq_nos, alice_moves, bob_duration)

    # bob_locator_packets = get_locator_packets(bob_experiment_log, bob_start)
    # bob_locator_throughputs = get_locator_throughuts(bob_locator_packets, bob_duration)
    # plot_throughputs(bob_locator_throughputs, bob_duration, "CN")
