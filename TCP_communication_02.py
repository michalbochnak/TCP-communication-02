"""
Michal Bochnak
CS 450, hw5
Spring 2018
April 21, 2018
"""


#
# Program builds upon TCP_communication_01.py and is improved in a way
# that multiple packets can be sent before receiving ACK (acknowledgement)
# from the receiver for each of the packets. Sender will resend only
# packets that were lost. Receiver will assemble the file at his end
# correctly even if packets were received out of order as order of the
# packets is marked by sender.
# Program simulates reliable transmission of a data file via unrealiable 
# connection protocol such as TCP (Transmission Control Protocol).
# It allows to specify different parameters to simulate
# data transfer in different scenarios. Data is send sequentially,
# i.e if packet was not received it will be resend untill it is received
# and no other packet will be send untill that is succesfull.
#
# usage: tester.py [-h] [-p PORT] [-l LOSS] [-d DELAY] [-b BUFFER] -f FILE
#                  [-r RECEIVE] [-s] [-v]
#
# Utility script for testing HW5 solutions under user set conditions.
#
# optional arguments:
# -h, --help            show this help message and exit
# -p PORT, --port PORT  The port to simulate the lossy wire on (defaults to
#                          9999).
# -l LOSS, --loss LOSS  The percentage of packets to drop.
# -d DELAY, --delay DELAY
#                         The number of seconds, as a float, to wait before
#                         forwarding a packet on.
# -b BUFFER, --buffer BUFFER
#                         The size of the buffer to simulate.
# -f FILE, --file FILE  The file to send over the wire.
# -r RECEIVE, --receive RECEIVE
#                         The path to write the received file to. If not
#                         provided, the results will be written to a temp file.
# -s, --summary         Print a one line summary of whether the transaction
#                         was successful, instead of a more verbose description
#                         of the result.
# -v, --verbose         Enable extra verbose mode.
#


import socket
import io
import time
import homework5
import homework5.logging


def rcv_bef(got_num, exc_num):
    """
    true if chunk was received already
    :param got_num:
    :param exc_num:
    :return:
    """
    if got_num - exc_num < 0:
        return True
    if got_num - exc_num > 100:
        return True
    return False


def send(sock: socket.socket, data: bytes):
    """
    Implementation of the sending logic for sending data over a slow,
    lossy, constrained network.

    Args:
        sock -- A socket object, constructed and initialized to communicate
                over a simulated lossy network.
        data -- A bytes object, containing the data to send over the network.
    """

    # Naive implementation where we chunk the data to be sent into
    # packets as large as the network will allow, and then send them
    # over the network, pausing half a second between sends to let the
    # network "rest" :)
    # logger = homework5.logging.get_logger("hw5-sender")
    chunk_size = homework5.MAX_PACKET - 1
    # pause = .1
    offsets = range(0, len(data), homework5.MAX_PACKET - 1)
    seq_num = 0
    estimated_rtt = 0
    dev_rtt = 0
    alpha = 0.125
    beta = 0.25
    sample_rtt = 1

    # send the chunks
    chunks = [data[i:i + chunk_size] for i in offsets]
    # print('Num of chunks: ', len(chunks))
    idx = 0
    buffer_size = 10
    while True:
        # calculate timeout
        estimated_rtt = ((1 - alpha) * estimated_rtt) + \
                        (alpha * sample_rtt)
        dev_rtt = ((1 - beta) * dev_rtt) + \
                  (beta * abs(sample_rtt - estimated_rtt))
        timeout_interval = estimated_rtt + (4 * dev_rtt)

        # send
        index = idx
        send_chunks = []
        temp_seq_num = seq_num
        for _ in range(0, buffer_size):
            # print("index: ", index, "chunks.len", len(chunks) - 1)
            bytes_to_send = bytes([temp_seq_num]) + chunks[index]
            # start the timer
            start_time = time.time()
            # print('sending seq: ', seq_num)
            sock.send(bytes_to_send)
            temp_seq_num = (temp_seq_num + 1) % 256
            send_chunks.append(bytes_to_send[0])
            if index < len(chunks) - 1:
                index = index + 1
            else:
                break
            # update sequence number

        # print('Send Chunks: ', send_chunks)

        # receive
        for _ in range(0, buffer_size):
            try:
                sock.settimeout(timeout_interval)
                answer = sock.recv(homework5.MAX_PACKET)
                # stop timer - sampled RTT
                sample_rtt = time.time() - start_time
                if answer[0] == send_chunks[0]:
                    # print('1. receiced ack: ', answer[0])
                    seq_num = (seq_num + 1) % 256
                    if idx < len(chunks) - 1:
                        idx = idx + 1
                    del send_chunks[0]
                    # last_valid_ack = answer[0]
                else:
                    break
            except socket.timeout:
                break

        # all acks received, increase buffer
        # if ((last_valid_ack + 1) == seq_num):
        #     if buffer_size < 40:
        #         buffer_size = buffer_size * 2
        # elif buffer_size > 1:
        #     buffer_size = buffer_size // 2

        # done
        # print ('seq_num: ', seq_num, "len(chunks); ", len(chunks))
        if seq_num == len(chunks):
            break

    # # done, send seq_num to FIN message
    # ack = False
    # while ack is False:
    #     # calculate timeout
    #     estimated_rtt = ((1 - alpha) * estimated_rtt) + (alpha * sample_rtt)
    #     dev_rtt = ((1 - beta) * dev_rtt) + \
    #               (beta * abs(sample_rtt - estimated_rtt))
    #     timeout_interval = estimated_rtt + (4 * dev_rtt)
    #     # start the timer
    #     start_time = time.time()
    #     sock.send(bytes([100]))
    #     sock.settimeout(timeout_interval)
    #     try:
    #         answer = sock.recv(homework5.MAX_PACKET)
    #         # stop timer - sampled RTT
    #         sample_rtt = time.time() - start_time
    #     except socket.timeout:
    #         continue
    #
    #     # make sure ACT is for the FIN message
    #     ack = bool(answer[0] == 100)


def recv(sock: socket.socket, dest: io.BufferedIOBase) -> int:
    """
    Implementation of the receiving logic for receiving data over a slow,
    lossy, constrained network.

    Args:
        sock -- A socket object, constructed and initialized to communicate
                over a simulated lossy network.

    Return:
        The number of bytes written to the destination.
    """
    # Naive solution, where we continually read data off the socket
    # until we don't receive any more data, and then return.
    num_bytes = 0
    received_chunks = []
    expected_chunk = 0
    last_ack = 0
    while True:
        # print('Received: ', received_chunks)
        data = sock.recv(homework5.MAX_PACKET)
        if not data:
            break
        # print("Received bytes: ", data[0], " -> ", len(data))
        # The chunk was not received yet
        # print('expected_chunk: ', expected_chunk, 'data[0]; ', data[0])
        if data[0] not in received_chunks and data[0] == expected_chunk:
            expected_chunk = expected_chunk + 1
            expected_chunk = expected_chunk % 256
            received_chunks.append(data[0])
            if len(received_chunks) > 240:
                received_chunks.pop(0)
            dest.write(data[1:])
            num_bytes += len(data[1:])
            dest.flush()
            # send ACT
            # print('20. sending ack: ', data[0])
            sock.send(bytes([data[0]]))
            last_ack = data[0]
        # ack lost, resent
        elif data[0] in received_chunks and rcv_bef(data[0], expected_chunk):
            # print('21. sending ack: ', data[0])
            sock.send(bytes([data[0]]))
        # Chunk was received before
        else:
            # print('22. sending ack: ', last_ack)
            sock.send(bytes([last_ack]))
    return num_bytes
