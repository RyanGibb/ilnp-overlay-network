import matplotlib.pyplot as plt
import matplotlib.ticker as plticker
import numpy as np
import sys
import time
import os
import ast

from math import floor, ceil, log10
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
    moves = []
    prev_interface = None
    prev_interface_elapsed = None
    for line in experiment_log[1:-3]:
        if line[0] == '\t':
            continue
        _, time_string, remote, direction, local, size, seq_num = line.split()
        time = datetime.strptime(time_string, "%H:%M:%S.%f")
        elapsed = (time - start).total_seconds()
        # if receiving
        if direction == "->":
            seq_no_times.append(elapsed)
            seq_no_values.append(int(seq_num))
        interface = remote.split("%")[1].split("]")[0]
        # If moving
        # Only check if more than 10 seconds since last move,
        # otherwise will get flipping back and forth from soft handoff
        if ((prev_interface_elapsed == None or elapsed - prev_interface_elapsed > 10)
                and interface != prev_interface):
            moves.append((prev_interface, elapsed))
            prev_interface = interface
            prev_interface_elapsed = elapsed
    # record last interface
    moves.append((interface, None))
    seconds = ceil((end - start).total_seconds())
    duration = ceil((end - start).total_seconds())
    return start, duration, (seq_no_times, seq_no_values), moves


def get_locator_packets(experiment_log, start, mobile=False):
    locator_packets = defaultdict(list)
    for line in experiment_log[1:-3]:
        if line[0] == '\t':
            continue
        _, time_string, remote, direction, local, size, seq_num = line.split()
        time = datetime.strptime(time_string, "%H:%M:%S.%f")
        elapsed = (time - start).total_seconds()
        size=int(size)

        # If alice, look at interface
        if mobile:
            interface = remote.split("%")[1].split("]")[0]
            locator = interface
        # If bob, look at remote loc
        else:
            remote_locator = ":".join(remote[1:].split("/")[1].split(":")[:4])
            locator = remote_locator
        
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
    # ax.set_xlim(0, seq_no_times[-1])
    # ax.set_ylim(0, seq_no_values[-1])
    # ax.set_xlim(left=0)
    # ax.set_ylim(bottom=0)
    title="Received sequence numbers vs Time on %s" % node
    # ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Sequence Number")
    # loc = plticker.MultipleLocator()
    # ax.xaxis.set_major_locator(loc)
    # ax.set_xticks(np.arange(0, seconds, step=seconds/10)) 
    # ax.set_yticks(np.arange(0, seq_no_values[-1], step=int(seq_no_values[-1])/10))
    # ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%0.1f'))
    # ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%0.1f'))
    # ax.scatter(np.array(seq_no_times), np.array(seq_no_values), s=0.001)
    ax.plot(np.array(seq_no_times), np.array(seq_no_values))
    
    ax.set_xlim(left=0, right=duration)
    ax.set_ylim(bottom=0)

    ax.set_xticks(np.arange(0, duration + 1, step=50))
    ax.grid(False, which="major", axis="x")
    # ax.set_yticks(np.arange(0, len(seq_nos) + 1, step=5000))

    # ax.yaxis.set_minor_locator(plticker.MultipleLocator(200))
    # ax.grid(True, which='minor')

    prev=0
    for from_loc, elapsed in moves:
        if elapsed == None:
            elapsed = seq_no_times[-1]
        else:
            ax.axvline(x=elapsed, linewidth=1, color='grey', linestyle='--')
        pos=(elapsed+prev)/2
        rot=0
        if elapsed-prev < 30:
            rot=90
        ax.text(pos,seq_no_values[-1]/2,from_loc,color='gray',rotation=rot,ha="center")
        prev=elapsed

    # ax.set_xticks([move[1] for move in moves[:-1]], minor=True)
    # ax.grid(True, which="minor", axis="x")

    fig.savefig(os.path.join(out_dir, '%s.pdf' % title))
    fig.savefig(os.path.join(out_dir, '%s.png' % title))

def plot_throughputs(locator_throughputs, duration, node):
    seconds_range = [i for i in range(0, duration, throughput_bucket_size)]
    
    max_throughout = max([max(throughput) for throughput in locator_throughputs.values()])
    
    # round max_throughout *up* to *even* 1 significant figure
    l = ceil(log10(max_throughout + 1)) # length, in base 10 digits
    max_throughout = ceil(max_throughout / 2 / 10 ** (l - 1)) * 10 ** (l - 1) * 2

    fig, axs = plt.subplots(len(locator_throughputs), sharex=True, sharey=True)
    
    # https://stackoverflow.com/questions/6963035/pyplot-axes-labels-for-subplots
    # add a big axes, hide frame
    # fig.add_subplot(111, frameon=False)
    # # hide tick and tick label of the big axes
    # plt.tick_params(labelcolor='none', top=False, bottom=False, left=False, right=False)
    # plt.grid(False)

    i = 0
    for locator, throughputs in locator_throughputs.items():
        axs[i].grid(color='lightgray', linestyle='-', linewidth=1)
        axs[i].set_axisbelow(True)
        # title="Throughput in %ds buckets vs Time on %s locator %s" % (throughput_bucket_size, node, locator)
        title="MN locator %s" % locator
        axs[i].set_title(title)
        # axs[i].set_xlabel("Time (s)")
        # axs[i].set_ylabel("Throughput (B/s)")
        
        axs[i].set_xticks(np.arange(0, duration + 1, step=50))
        axs[i].set_yticks(np.arange(0, max_throughout + 1, step=max_throughout/4))

        axs[i].xaxis.set_minor_locator(plticker.MultipleLocator(10))
        axs[i].yaxis.set_minor_locator(plticker.MultipleLocator(max_throughout/8))

        axs[i].plot(np.array(seconds_range), np.array(throughputs),  label=locator)
        axs[i].set_xlim(left=0, right=duration)
        axs[i].set_ylim(bottom=0, top=max_throughout)
        # axs[i].set_ylim(bottom=0)

        axs[i].grid(True, which='minor')
    
        # axs[i].legend()

        i += 1
    
    # Set common labels
    # fig.text(0.5, 0.01, 'Time (s)', ha='center', va='center')
    # fig.text(0.01, 0.5, 'Throughput (B/s)', ha='center', va='center', rotation='vertical')


    # plt.setp(axs[:], xlabel='Time (s)')
    # plt.setp(axs[:], ylabel='Throughput (B/s)')
    # plt.xlabel("Time (s)")
    # plt.ylabel("Throughput (B/s)", y)
    fig.supxlabel('Time (s)')
    fig.supylabel('Throughput (kB/s)')

    title="Throughput in %ds buckets vs Time on %s" % (throughput_bucket_size, node)
    fig.savefig(os.path.join(out_dir, '%s.pdf' % title))
    fig.savefig(os.path.join(out_dir, '%s.png' % title))


if __name__ == "__main__":
    log_dir = sys.argv[1]
    global out_dir
    out_dir = log_dir

    global throughput_bucket_size
    throughput_bucket_size = 1

    alice_experiment_log = open(os.path.join(log_dir, "experiment_alice.log"), "r").readlines()
    bob_experiment_log   = open(os.path.join(log_dir, "experiment_bob.log"  ), "r").readlines()
    

    alice_start, alice_duration, alice_seq_nos, alice_moves = get_seq_nos(alice_experiment_log)
    if alice_seq_nos != ([], []):
        plot_seq_nos("MN", alice_seq_nos, alice_moves, alice_duration)
    
    bob_start, bob_duration, bob_seq_nos, bob_moves = get_seq_nos(bob_experiment_log)
    if bob_seq_nos != ([], []):
        plot_seq_nos("CN", bob_seq_nos, alice_moves, bob_duration)

    alice_locator_packets = get_locator_packets(alice_experiment_log, alice_start, mobile=True)
    alice_locator_throughputs = get_locator_throughuts(alice_locator_packets, alice_duration)
    plot_throughputs(alice_locator_throughputs, alice_duration, "MN")

    bob_locator_packets = get_locator_packets(bob_experiment_log, bob_start)
    bob_locator_throughputs = get_locator_throughuts(bob_locator_packets, bob_duration)
    plot_throughputs(bob_locator_throughputs, bob_duration, "CN")
