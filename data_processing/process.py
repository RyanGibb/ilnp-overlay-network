import matplotlib.pyplot as plt
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

if __name__ == "__main__":
    log_dir = sys.argv[1]
    cn = sys.argv[2]
    mn = sys.argv[3]
    experiment_log = open(os.path.join(log_dir, "experiment_%s.log" % cn), "r").readlines()
    network_log = open(os.path.join(log_dir, "network_%s.log" % mn), "r").readlines()
    times = []
    seq_nums = []
    start_string = experiment_log[6].split()[1]
    end_string   = experiment_log[-3].split()[1]
    start = datetime.strptime(start_string, "%H:%M:%S.%f")
    end   = datetime.strptime(end_string, "%H:%M:%S.%f")
    for line in experiment_log[5:-3]:
        date, time_string, remote, _, size, seq_num = line.split()
        time = datetime.strptime(time_string, "%H:%M:%S.%f")
        secs_since_start = (time - start).total_seconds()
        times.append(secs_since_start)
        seq_nums.append(int(seq_num))
    seconds = math.ceil((end - start).total_seconds())
    
    moves = []
    interface_packets = defaultdict(list)
    for line in network_log[6:]:
        if "Moving from" in line:
            date, time_string, _, _, from_locs, _, to_locs = line.split()
            from_loc = ast.literal_eval(from_locs)[0]
            to_loc = ast.literal_eval(to_locs)[0]
            time = datetime.strptime(time_string, "%H:%M:%S.%f")
            secs_since_start = (time - start).total_seconds()
            moves.append((from_loc, secs_since_start))
        elif "Error" not in line:
            date, time_string, ilv1, direction, ilv2, _, size, next_header, hop_limit, _ = line.split()[:10]
            time = datetime.strptime(time_string, "%H:%M:%S.%f")
            secs_since_start = (time - start).total_seconds()
            size=int(size[:-1])
            next_header=int(next_header[:-1])
            hop_limit=int(hop_limit[:-1])
            _, interface = ilv1.split("%")
            interface_packets[interface].append((secs_since_start, size))
    

    throughput_window_size = 2
    interface_throughputs = {}
    for interface, packets in interface_packets.items():
        throughputs = []
        for i in range(0, seconds, throughput_window_size):
            window = 0
            for secs_since_start, size in packets:
                if secs_since_start > i and secs_since_start < i + throughput_window_size:
                    window += size
            throughputs.append(window / throughput_window_size)
        interface_throughputs[interface] = throughputs

    


            
    

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.grid(color='lightgray', linestyle='-', linewidth=1)
    ax.set_axisbelow(True)
    ax.set_xlim(0, seconds)
    ax.set_ylim(0, seq_nums[-1])
    title="Sequence numbers vs Time on CN"
    ax.set_title(title)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Sequence Number")
    
    ax.set_xticks(np.arange(0, seconds, step=60)) 
    ax.set_yticks(np.arange(0, seq_nums[-1], step=1000))

    ax.plot(np.array(times), np.array(seq_nums))

    for from_loc, secs_since_start in moves:
        if secs_since_start > seconds:
            break
        ax.axvline(x=secs_since_start, color='gray', linestyle='--')
        ax.text(secs_since_start-50,seq_nums[-1]/2+10,from_loc,color='gray',rotation=0)

    fig.savefig('data_processing/%s.png' % title)

    throughuts = interface_throughputs.values()
    aggregate_throughput = []
    for i in range(0, seconds, throughput_window_size):
        x=sum(throughut[int(i/throughput_window_size)] for throughut in throughuts)
        aggregate_throughput.append(x)
    interface_throughputs["aggregate"] = aggregate_throughput


    seconds_range = [i for i in range(1, seconds + 1, throughput_window_size)]
    for interface, throughputs in interface_throughputs.items():
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.grid(color='lightgray', linestyle='-', linewidth=1)
        ax.set_axisbelow(True)
        ax.set_xlim(0, seconds)
        ax.set_ylim(0, 20000)
        title="%ds Moving average throughput vs Time on MN %s" % (throughput_window_size, interface)
        ax.set_title(title)
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Throughput (b/s)")
        
        ax.set_xticks(np.arange(1, seconds + 1, step=60)) 
        # ax.set_yticks(np.arange(0, 20000, step=1000))

        ax.plot(np.array(seconds_range), np.array(throughputs), label=interface)
    
        ax.legend()

        fig.savefig('data_processing/%s.png' % title)
