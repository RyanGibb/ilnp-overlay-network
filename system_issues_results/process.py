import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import numpy as np
import sys
import time
import os
import ast

from datetime import datetime
from collections import defaultdict
from statistics import mode
from math import ceil, log10

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
    seconds = ceil((end - start).total_seconds())
    duration = ceil((end - start).total_seconds())
    return start, duration, (seq_no_times, seq_no_values)


# Get moves (locators and timestamps) from mobile node network
def get_moves(start, network_log):
    moves = []
    elapsed = None
    for line in network_log[1:]:
        if "Moving from" in line:
            _, time_string, _, _, from_locs, _, to_locs = line.split()
            from_loc = ast.literal_eval(from_locs)[0]
            to_loc = ast.literal_eval(to_locs)[0]
            time = datetime.strptime(time_string, "%H:%M:%S.%f")
            prev_interface_elapsed = elapsed
            elapsed = (time - start).total_seconds()
            moves.append((from_loc, elapsed))
    if elapsed - prev_interface_elapsed > 10:
        # record last locator
        moves.append((to_loc, None))
    return moves


def get_locator_packets(experiment_log, start, received_locs=True, sent_locs=True, remote=True):
    locator_packets = defaultdict(list)
    for line in experiment_log[1:-3]:
        if line[0] == '\t':
            continue
        _, time_string, remote_addrinfo, direction, local_addrinfo, size, seq_num = line.split()
        time = datetime.strptime(time_string, "%H:%M:%S.%f")
        elapsed = (time - start).total_seconds()
        size=int(size)

        if remote:
            addrinfo = remote_addrinfo
        else:
            addrinfo = local_addrinfo
        
        if (direction == "->" and received_locs) or (direction == "<-" and sent_locs):
            locator = ":".join(addrinfo[1:].split("/")[1].split(":")[:4])
            locator_packets[locator].append((elapsed, size))
    return locator_packets


def get_locator_throughuts(locator_packets, end):
    locator_throughputs = {}
    for locator, packets in locator_packets.items():
        throughputs = []
        for i in range(0, end, throughput_bucket_size):
            window = 0
            for elapsed, size in packets:
                if (elapsed > i - throughput_bucket_size / 2 and
                    elapsed < i + throughput_bucket_size / 2):
                    window += size
            # make kB
            window /= 1000
            throughputs.append(window)
        locator_throughputs[locator] = throughputs
    throughputs = locator_throughputs.values()
    aggregate_throughput = []
    for i in range(0, int(end / throughput_bucket_size)):
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
    title="Received sequence numbers vs Time on %s" % node
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Sequence Number")
    ax.scatter(np.array(seq_no_times), np.array(seq_no_values), s=0.1)
    
    ax.set_xlim(left=0, right=duration)
    ax.set_ylim(bottom=0)

    ax.set_xticks(np.arange(0, duration + 1, step=50))
    ax.grid(False, which="major", axis="x")

    prev=0
    for from_loc, elapsed in moves:
        if elapsed == None:
            elapsed = seq_no_times[-1]
        elif elapsed > seq_no_times[-1]:
            continue
        else:
            ax.axvline(x=elapsed, linewidth=1, color='grey', linestyle='--')
        pos=elapsed-(elapsed-prev)/2
        rot=0
        if elapsed-prev < 30:
            rot=90
        ax.text(pos,seq_no_values[-1]/2,from_loc,color='gray',rotation=rot,ha="center")
        prev=elapsed

    fig.savefig(os.path.join(out_dir, '%s.pdf' % title))
    fig.savefig(os.path.join(out_dir, '%s.png' % title))

def plot_throughputs(locator_throughputs, duration, node):
    seconds_range = [i for i in range(0, duration, throughput_bucket_size)]
    
    mode_throughput = mode(t for throughputs in locator_throughputs.values() for t in throughputs if t != 0)
    max_throughput = mode_throughput
    print(mode_throughput)
    
    # round max_throughput *up* to *even* 1 significant figure
    l = ceil(log10(max_throughput + 1)) # length, in base 10 digits
    max_throughput = ceil(max_throughput / 2 / 10 ** (l - 1)) * 10 ** (l - 1) * 2

    fig, axs = plt.subplots(len(locator_throughputs), sharex=True, sharey=True)

    i = 0
    for locator, throughputs in locator_throughputs.items():
        axs[i].grid(color='lightgray', linestyle='-', linewidth=1)
        axs[i].set_axisbelow(True)
        title="MN locator %s" % locator
        axs[i].set_title(title)
        
        axs[i].set_xticks(np.arange(0, duration + 1, step=50))
        axs[i].set_yticks(np.arange(0, max_throughput + 1, step=max_throughput/4))

        axs[i].xaxis.set_minor_locator(plticker.MultipleLocator(10))
        axs[i].yaxis.set_minor_locator(plticker.MultipleLocator(max_throughput/8))

        axs[i].plot(np.array(seconds_range), np.array(throughputs),  label=locator)
        axs[i].set_xlim(left=0, right=duration)
        axs[i].set_ylim(bottom=0, top=max_throughput)

        axs[i].grid(True, which='minor')
        i += 1
    fig.supxlabel('Time (s)')
    fig.supylabel('Throughput (kB/s)')

    title="Throughput in %ds buckets vs Time on %s" % (throughput_bucket_size, node)
    fig.savefig(os.path.join(out_dir, '%s.pdf' % title))
    fig.savefig(os.path.join(out_dir, '%s.png' % title))


def get_seq_nos_to_locs(experiment_log, mobile=True):
    seq_nos_to_locs = {}
    for line in experiment_log[1:-3]:
        if line[0] == '\t':
            continue
        _, time_string, remote_addrinfo, direction, local_addrinfo, size, seq_num = line.split()
        if direction == "->":
            if mobile:
                addrinfo = remote_addrinfo
            else:
                addrinfo = local_addrinfo
            locator = ":".join(addrinfo[1:].split("/")[1].split(":")[:4])
            seq_nos_to_locs[seq_num] = locator
    return seq_nos_to_locs


def get_sent_locator_packets(experiment_log, seq_nos_to_locs, start):
    locator_packets = defaultdict(list)
    for line in experiment_log[1:-3]:
        if line[0] == '\t':
            continue
        _, time_string, remote_addrinfo, direction, local_addrinfo, size, seq_num = line.split()
        if direction == "<-":
            time = datetime.strptime(time_string, "%H:%M:%S.%f")
            elapsed = (time - start).total_seconds()
            size=int(size)
            locator = seq_nos_to_locs.get(seq_num)
            if locator != None:
                locator_packets[locator].append((elapsed, size))
    return locator_packets


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: $ python3 process.py <experiment log directory>")
        exit(0)
    log_dir = sys.argv[1]
    global out_dir
    out_dir = log_dir

    global throughput_bucket_size
    throughput_bucket_size = 1

    alice_experiment_log = open(os.path.join(log_dir, "experiment_alice.log"), "r").readlines()
    alice_network_log    = open(os.path.join(log_dir, "network_alice.log"   ), "r").readlines()
    bob_experiment_log   = open(os.path.join(log_dir, "experiment_bob.log"  ), "r").readlines()
    bob_network_log      = open(os.path.join(log_dir, "network_bob.log"     ), "r").readlines()
    

    alice_start, alice_duration, alice_seq_nos = get_seq_nos(alice_experiment_log)
    alice_moves = get_moves(alice_start, alice_network_log)
    if alice_seq_nos != ([], []):
        plot_seq_nos("MN", alice_seq_nos, alice_moves, alice_duration)
    
    bob_start, bob_duration, bob_seq_nos = get_seq_nos(bob_experiment_log)
    if bob_seq_nos != ([], []):
        plot_seq_nos("CN", bob_seq_nos, alice_moves, bob_duration)

    # To determine locator of packet sent from alice,
    # requires cross referencing with bob

    alice_recieved_locator_packets = get_locator_packets(alice_experiment_log, alice_start, sent_locs=False, remote=False)
    alice_sent_seq_nos_to_locs = get_seq_nos_to_locs(bob_experiment_log)
    alice_sent_locator_packets = get_sent_locator_packets(alice_experiment_log, alice_sent_seq_nos_to_locs, alice_start)
    alice_locator_packets = defaultdict(list)

    for locator, loctor_packets in alice_recieved_locator_packets.items():
        alice_locator_packets[locator] += loctor_packets
    for locator, loctor_packets in alice_sent_locator_packets.items():
        alice_locator_packets[locator] += loctor_packets
    # alice_locator_packets = alice_sent_locator_packets
    sorted_alice_locator_packets = {}
    for locator, loctor_packets in alice_locator_packets.items():
        # locator_packets = [(elapsed, size)]
        loctor_packets = sorted(loctor_packets, key=lambda x: x[0])
        sorted_alice_locator_packets[locator] = loctor_packets

    alice_locator_throughputs = get_locator_throughuts(sorted_alice_locator_packets, alice_duration)
    plot_throughputs(alice_locator_throughputs, alice_duration, "MN")

    bob_locator_packets = get_locator_packets(bob_experiment_log, bob_start)
    bob_locator_throughputs = get_locator_throughuts(bob_locator_packets, bob_duration)
    plot_throughputs(bob_locator_throughputs, bob_duration, "CN")
