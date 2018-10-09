# Dropzone Action Info
# Name: Memobird
# Description: Send to Memobird Printer
# Handles: Files, Text
# Creator: Just4test
# URL: https://github.com/Just4test/Memobird.dzbundle
# Events: Dragged, Clicked
# OptionsNIB: UsernameAPIKey
# KeyModifiers: Command, Option, Control, Shift
# SkipConfig: Yes
# RunsSandboxed: Yes
# Version: 1.0
# MinDropzoneVersion: 3.5
# PythonPath: /usr/local/bin/python3


import sys
if not ('packages' in sys.path):
	sys.path.insert(0, 'packages')
if not ('packages.zip' in sys.path):
	sys.path.insert(0, 'packages.zip')



from PIL import Image
from io import BytesIO
from base64 import b64encode
from plistlib import readPlist
import qrcode



DEVICE_WIDTH = 384

class Paper:

	def __init__(self):
		self.contents = []

	def add_txt(self, txt):
		self.contents.append(['T', txt])

	def add_img_data(self, img):
		# 图片宽度最大支持384。支持黑白图（色深1位），并且这个傻逼玩意打出来的图片是上下颠倒的。
		# 上下翻转
		img = img.transpose(Image.FLIP_TOP_BOTTOM)
		# 缩放
		width, height = img.size
		if width > DEVICE_WIDTH:
			new_height = int(height * DEVICE_WIDTH / width)
			img = img.resize((DEVICE_WIDTH, new_height), Image.BILINEAR)

		img.load()

		#对于透明图片，使用白色背景
		if len(img.split()) == 4:
			temp = Image.new("RGB", img.size, (255, 255, 255))
			print(img.split(), len(img.split()))
			temp.paste(img, mask=img.split()[3])
			img = temp

		#转换为黑白图
		img = img.convert('1')
		bmp_data = BytesIO()
		img.save(bmp_data, 'BMP')
		#文本和图片之间需要有一个换行，否则文本会挤到图片的下方
		if len(self.contents) > 0 and self.contents[-1][0] == 'T' and self.contents[-1][1][-1] != '\n':
			self.contents[-1][1] += '\n'
		self.contents.append(('P', bmp_data.getvalue()))

	def add_img_file(self, path):
		self.add_img_data(Image.open(path))

	def add_url(self, url):
		self.add_txt(url)
		self.add_img_data(qrcode.make(url))

	def encode(self):
		def encodeone(v):
			if v[0] == 'T':
				return 'T:' + b64encode(v[1].encode('gbk')).decode('ascii')
			elif v[0] == 'P':
				return 'P:' + b64encode(v[1]).decode('ascii')

		return '|'.join([encodeone(c) for c in self.contents])


import os
MEMOBIRD_ACCESS_KEY = '539d2e325c1744a28bcf232e0c651993'
MEMOBIRD_DEVICE_ID = os.environ.get('username')
MEMOBIRD_USER_ID = os.environ.get('USER_ID')
CLOUDCONVERT_KEY = os.environ.get('api_key')

import requests
import time


def get_userid(access_key, device_id):
	temp = os.environ.get('memobird_userid', '').split(':')
	if len(temp) == 2 and temp[0] == device_id:
		return temp[1]

	try:
		response = requests.post(
			url="http://open.memobird.cn/home/setuserbind",
			data={
				'ak': access_key,
				'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
				'memobirdID': device_id,
			},
		)
		if response.status_code != 200 or response.json().get('showapi_res_code') != 1:
			dz.error('Can\'t bind user', 'Server response:\n{}'.format(response.text))
		user_id = response.json()['showapi_userid'];
		dz.save_value('memobird_userid', '{}:{}'.format(device_id, user_id))
		return user_id
	except requests.exceptions.RequestException:
		dz.error('Can\'t bind user', 'HTTP Request failed.')

def clean_userid():
	dz.save_value('memobird_userid', '')


def print_paper(access_key, device_id, user_id, data):
	try:
		response = requests.post(
			url="http://open.memobird.cn/home/printpaper",
			data={
				'ak': access_key,
				'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
				'memobirdID': device_id,
				'userID': user_id,
				'printcontent': data,
			},
		)
		if response.status_code != 200 or response.json().get('showapi_res_code') != 1:
			clean_userid()
			dz.error('Can\'t print note', 'Server response:\n{}'.format(response.text))

		return response.json()['printcontentid'];
	except requests.exceptions.RequestException:
		dz.error('Can\'t print note', 'HTTP Request failed.')


def dragged():
	dz.begin('Binding device...')
	user_id = get_userid(MEMOBIRD_ACCESS_KEY, MEMOBIRD_DEVICE_ID)

	dz.begin('Creating paper data...')
	dragged_type = os.environ['dragged_type']
	paper = Paper()
	if dragged_type == 'text':
		for item in items:
			if item.find('http://') == 0 or item.find('https://') == 0:
				paper.add_url(item)
			else:
				paper.add_txt(item)
	else:
		def get_extname(path):
			temp = os.path.basename(path).split('.')
			if len(temp) > 1:
				return temp[-1].lower()
			else:
				return None
		for path in items:
			if not os.path.isfile(path):
				dz.error('Error', '{} is not a file.'.format(path))
			extname = get_extname(path)
			if extname in ['bmp', 'jpg', 'jpeg', 'png', 'gif']:
				paper.add_img_file(path)
			elif extname in ['txt', 'md']:
				paper.add_txt(open(path).read())
			elif extname == 'webloc':
				url = readPlist(path)['URL']
				print(url)
				paper.add_url(url)
			elif extname == 'pdf':
				# $PATH in Dropzone script set to "/usr/bin:/bin:/usr/sbin:/sbin",
				# but poppler usually install to /usr/local/bin/
				__import__('os').environ['PATH'] += ':/usr/local/bin/'
				try:
					pdf2image = __import__('pdf2image')
					images = pdf2image.convert_from_path(path)
				except Exception as e:
					info = 'Can`t call module pdf2image.'
					info += '\nTo print pdf, you need install poppler-utils. See:'
					info += '\nhttp://macappstore.org/poppler/'
					info += '\n\n' + repr(e)
					dz.error('Error', info)
				for image in images:
					paper.add_img_data(image)
			else:
				dz.error('Error', '{} Can\'t be print.'.format(path))


	dz.begin("Sending paper...")
	print(paper.encode())
	paper_id = print_paper(MEMOBIRD_ACCESS_KEY, MEMOBIRD_DEVICE_ID, user_id, paper.encode())
	dz.finish("Task Complete")
	dz.url(False)

	# You should always call dz.url or dz.text last in your script. The below dz.text line places text on the clipboard.
	# If you don't want to place anything on the clipboard you should still call dz.url(false)
#	dz.text("Here's some output which will be placed on the clipboard")
