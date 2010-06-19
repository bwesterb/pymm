#!/usr/bin/env python
# This is a very specific e-mail (de)multiplexer.  It's main use case is to
# filter all e-mail for a domain through a single e-mail address.
#
# This script is installed as the handler for all mail on a domain `pre-domain'
# and as the handler of all mail for a single `post-address'.  An e-mail
# handled for foo@pre-domain is tagged and forwarded to `filter-address'.  If
# this tagged e-mail is returned to post-address, it is forwarded to
# foo@target-domain.
#
#     (c) 2010 - Bas Westerbaan <bas@westerbaan.name>

import email.generator
import email.parser
import subprocess
import cStringIO
import traceback
import optparse
import fcntl
import time
import json
import sys
import os

def email_from_file(f):
	p = email.parser.FeedParser()
	while True:
		tmp = f.read(2048)
		if tmp == '':
			break
		p.feed(tmp)
	return p.close()

class Program(object):
	def parse_cmdline(self):
		parser = optparse.OptionParser()
		parser.add_option('-f', '--filter-address',
					dest='filter_address',
				  help="Use EMAIL as filter", metavar='EMAIL')
		parser.add_option('-L', '--log-to', dest='logTo',
				  default='/var/log/pymm',
				  help="Log to FILE", metavar='FILE')
		parser.add_option('-p', '--pre-domain', dest='pre_domain',
				  help="Use DOMAIN as pre domain",
				  metavar='DOMAIN')
		parser.add_option('-P', '--post-address', dest='post_address',
				  help="Use EMAIL as post address",
				  metavar='EMAIL')
		parser.add_option('-t', '--target-domain', dest='target_domain',
				  help="Use DOMAIN as target domain",
				  metavar='DOMAIN')
		parser.add_option('-x', '--header-key', dest='header_key',
				  default='X-37-For',
				  help="Use KEY as header key", metavar='KEY')
		return parser.parse_args()

	def error(self, message):
		message = {'type': 'error',
			   'message': message}
		self.log(message)
	
	def exception(self, message):
		io = cStringIO.StringIO()
		traceback.print_exc(file=io)
		message = {'type': 'exception',
			   'message': message,
			   'traceback': io.getvalue() }
		self.log(message)

	def log(self, message):
		message.setdefault('time', time.time())
		message.setdefault('pid', os.getpid())
		with open(self.options.logTo, 'a') as f:
			fcntl.flock(f, fcntl.LOCK_EX)
			try:
				f.seek(0, 2)
				f.write(json.dumps(message))
				f.write("\n")
			finally:
				fcntl.flock(f, fcntl.LOCK_UN)

	def main(self):
		self.options, self.args = self.parse_cmdline()
		try:
			if len(self.args) != 1:
				self.error("No command specified")
				return -1
			if self.args[0] == 'pre':
				return self.do_pre()
			if self.args[0] == 'post':
				return self.do_post()
			self.error("No such command: %s" % self.args[0])
			return -2
		except Exception as e:
			self.exception("Uncatched exception")
			return -3

	def do_pre(self):
		if not 'RPLINE' in os.environ:
			self.error("Missing RPLINE env variable")
			return -4
		if not 'DTLINE' in os.environ:
			self.error("Missing DTLINE env variable")
			return -5
		dt_prefix = 'Delivered-To: %s-' % self.options.pre_domain
		dt_line = os.environ['DTLINE'][:-1]
		if not dt_line.startswith(dt_prefix) or not \
				dt_line.endswith(self.options.pre_domain):
			self.error("Incorrect DTLINE: `%s'" % dt_line)
			return -6
		rp_prefix = 'Return-Path: '
		rp_line = os.environ['RPLINE'][:-1]
		if not rp_line.startswith(rp_prefix):
			self.error("Incorrect RPLINE: `%s'" % rp_line)
			return -7
		rp = rp_line[len(rp_prefix):]
		to = dt_line[len(dt_prefix):-len(self.options.pre_domain)-1]
		m = email_from_file(sys.stdin)
		if self.options.header_key in m:
			self.warn("`%s' already in e-mail header" %
					self.options.header_key)
		_from = m['From']
		_id = m['Message-ID']
		self.log({'type': 'pre',
			  'to': to,
			  'from': _from,
			  'rp': rp,
			  'id': _id})
		p = subprocess.Popen(['qmail-inject', '--',
					self.options.filter_address],
					stdin=subprocess.PIPE)
		p.stdin.write("%s: %s@%s\n" % (self.options.header_key, to, rp))
		p.stdin.write("Delivered-To: %s@%s\n" % (
					to, self.options.pre_domain))
		p.stdin.write("Return-Path: %s\n" % rp)
		del m['Return-Path']
		g = email.generator.Generator(p.stdin)
		g.flatten(m)
		p.stdin.close()
		if not p.wait() == 0:
			self.error("qmail-inject did not return 0")
			return -8
		self.log({'type': 'pre done'})
		return 0

	def do_post(self):
		if not 'RPLINE' in os.environ:
			self.error("Missing RPLINE env variable")
			return -4
		if not 'DTLINE' in os.environ:
			self.error("Missing DTLINE env variable")
			return -5
		post_domain = self.options.post_address.split('@',1)[-1]
		dt_should_be = 'Delivered-To: %s-%s' % (post_domain,
						self.options.post_address)
		dt_line = os.environ['DTLINE'][:-1]
		if not dt_line == dt_should_be:
			self.error("Incorrect DTLINE: `%s'" % dt_line)
			return -6
		m = email_from_file(sys.stdin)
		if not self.options.header_key in m:
			self.error("`%s' not in e-mail header" %
					self.options.header_key)
			return -9
		to, rp = m[self.options.header_key].split('@', 1)
		_from = m['From']
		_id = m['Message-ID']
		target = '%s@%s' % (to, self.options.target_domain)
		self.log({'type': 'post',
			  'to': to,
			  'from': _from,
			  'rp': rp,
			  'id': _id})
		p = subprocess.Popen(['qmail-inject', '--', target],
					stdin=subprocess.PIPE)
		p.stdin.write('Return-Path: %s\n' % rp)
		p.stdin.write('Delivered-To: %s\n' % target)
		del m['Return-Path']
		g = email.generator.Generator(p.stdin)
		g.flatten(m)
		p.stdin.close()
		if not p.wait() == 0:
			self.error("qmail-inject did not return 0")
			return -8
		self.log({'type': 'post done'})
		return 0
	
if __name__ == '__main__':
	Program().main()
	sys.exit(0) # Always exit OK
