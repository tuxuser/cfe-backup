#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import division
from optparse import OptionParser

import serial
import sys
import re
import binascii

lineregex = re.compile(r'([0-9a-fA-F])+: .*')
lineregex = re.compile(r'([0-9a-fA-F])+: (.*)')

def serread(ser, count):
    data = ser.read(count)
    #print(data)
    return data

def serwrite(ser, data):
    return ser.write(data)

def serreadline(ser):
    data = ser.readline()
    #print(data)
    return data

def printf(string):
	sys.stdout.write(string)
	sys.stdout.flush()

def skip_prompt(ser):
	while serread(ser, 1):
		pass

def wait_prompt(ser):
	printf("Waiting for a prompt...")
	while True:
		serwrite(ser, b'\x03')
		if(serread(ser, 1) == b'C' and serread(ser, 1) == b'F' and serread(ser, 1) == b'E' and serread(ser, 1) == b'>'):
			skip_prompt(ser)
			printf(" OK\n")
			return

def memreadblock(ser, addr, size):
	skip_prompt(ser)
	serwrite(ser, b'db %x %d\r' %(addr, size))
	serreadline(ser)
	buf = b''
	m = True
	total_size = size
	pos = 0
	while m:
		read_count = min(16, total_size - pos)
		line = serreadline(ser).strip().decode('utf8')
		m = lineregex.match(line)
		if not m:
			break

		bytes = [binascii.unhexlify(x) for x in m.group(0)[10:].split(' ')[0:read_count]]
		buf += b''.join(bytes)
	return buf

def memreadblock2file(ser, fd, addr, size):
	while True:
		buf = memreadblock(ser, addr, size)
		if len(buf) == size:
			break
		printf(' [!]\n')
	printf(' [.]\n')
	fd.write(buf)
	return

def memread(ser, path, addr, size, block):
	wait_prompt(ser)
	total_size = size
	fd = open(path, "wb")
	while size > 0:
		cur_size = (total_size - size)
		printf('%d%% (%d/%d)' %((cur_size / total_size) * 100, cur_size, total_size))
		if size > block:
			memreadblock2file(ser, fd, addr, block)
			size -= block
			addr += block
		else:
			memreadblock2file(ser, fd, addr, size)
			size = 0
	fd.close()
	return

def memwriteint(ser, data, addr, size):
	# byteswap
	swapped = binascii.hexlify(data[::-1]).decode('utf8')

	skip_prompt(ser)
	cmd = 'sm %x 0x%s %d\r' %(addr, swapped, size)
	serwrite(ser, cmd.encode('utf8'))

	serreadline(ser) # Skip command line
	
	written_bytes_hex = serreadline(ser).decode('utf8').split(' ')[1]
	if written_bytes_hex != swapped:
		print('retry...')
		memwriteint(ser, data, addr, size)
	
	cmd_status = serreadline(ser)
	if cmd_status != b'*** command status = 0\r\n':
		print('Invalid cmd status: %s' % cmd_status)

def memwritefile2int(ser, fd, addr, size):
	data = fd.read(size)
	memwriteint(ser, data, addr, size)
	printf(' [.]\n')

def memwrite(ser, path, addr):
	wait_prompt(ser)
	fd = open(path, "rb")
	fd.seek(0, 2) # End of stream
	size = fd.tell()
	fd.seek(0, 0) # Start of stream
	printf('Writing data of %d bytes @ 0x%x\n' % (size, addr))
	total_size = size

	while size > 0:
		cur_size = (total_size - size)
		printf('%d%% (%d/%d)' %((cur_size / total_size) * 100, cur_size, total_size))
		if (size // 4) > 0:
			write_size = 4
		else:
			write_size = 1

		memwritefile2int(ser, fd, addr, write_size)
		size -= write_size
		addr += write_size
	
	fd.close()

def main():
	optparser = OptionParser("usage: %prog [options]",version="%prog 0.1")
	optparser.add_option("--block", dest="block", help="buffer block size", default="10240",metavar="block")
	optparser.add_option("--serial", dest="serial", help="specify serial port", default="/dev/ttyUSB0", metavar="dev")
	optparser.add_option("--read", dest="read", help="read mem to file", metavar="path")
	optparser.add_option("--write", dest="write", help="write data to mem", metavar="write")
	optparser.add_option("--addr", dest="addr",help="mem address", metavar="addr")
	optparser.add_option("--size", dest="size",help="size to copy", metavar="bytes")
	(options, args) = optparser.parse_args()
	if len(args) != 0:
		optparser.error("incorrect number of arguments")
	ser = serial.Serial(options.serial, 115200, timeout=1)
	if options.read and options.write:
		optparser.error("Cannot read and write in same call!")
	elif options.read:
		memread(ser, options.read, int(options.addr, 0), int(options.size, 0), int(options.block, 0))
	elif options.write:
		memwrite(ser, options.write, int(options.addr, 0))
	return

if __name__ == '__main__':
	main()
