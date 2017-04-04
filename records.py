#!/usr/bin/env python
#-*-coding:utf-8-*-

import os, re, time, base64, zlib, binascii, hashlib, random, string

class Records:
  def __init__(self, www_dir = "./", record_dir = 'recordings/', record_list = 'records.js',
      record_html = 'records.html', slice_size = 256, compress_level = 9,
      slice_str = '=-+-+=', min_frames = 35, max_frames = 45, novnc_player = '/vplayer/',
      action = ('remove', 'zb64', 'slice', 'md_default', 'md', 'restore_raw', 'remove_raw')):

    self.www_dir = www_dir
    self.record_dir = record_dir
    self.record_list = record_list
    self.record_html = record_html
    # in KB
    self.slice_size = slice_size * 1024
    self.compress_level = compress_level
    self.slice_str = slice_str
    # Ensure frames eough for play several seconds
    self.min_frames = min_frames
    self.max_frames = max_frames
    self.action = action
    self.novnc_player = novnc_player

    self.raw = "raw"
    self.zb64 = "nvz"
    self.slice = "nvs"
    self.slices = "nvs."
    self.post_md = "post.md"
    self.session_md = "session.md"

  def suffix(self, rtype):
    return "." + rtype

  def abspath(self, path = '', rtype = ''):
    path = self.record_dir + path
    if rtype: path = path + self.suffix(rtype)
    #return os.path.abspath(path)
    return path

  def format_ctime(self, ctime, format):
    return time.strftime(format, time.gmtime(ctime))

  def generate_markdown(self, rec, info, rtype = ''):
    def md5(str):
      h = hashlib.md5()
      h.update(str)
      return h.hexdigest()

    record_create = self.format_ctime(string.atof(info['create']), "%Y-%m-%d-%H-%M-%S-")
    post_link = (record_create + info['title'] + "-" + info['time']).replace("  ", " ").replace(" ", "-").replace(":", "-").lower()
    record_session = md5(post_link)

    orig_rec = rec
    if os.path.dirname(rec):
      rec = os.path.dirname(rec) + '/' + record_create + os.path.basename(rec)
    else:
      rec = record_create + os.path.basename(rec)
    rec = rec.replace(self.suffix(self.zb64), '').replace(self.suffix(self.slice), '')

    post_content = "layout: post\n"
    post_content += "session: /%s/\n" % record_session
    post_content += "permalink: /%s/\n" % post_link
    post_content += "fullscreen: true\n"

    # If the target dir is a subdirectory, then, prepend the root recording directory
    record_dir = os.path.abspath(self.record_dir.replace('//', '/')).replace(os.path.abspath(self.www_dir) + '/', '')

    record_data = orig_rec.replace(self.suffix(self.zb64), '')
    if rtype:
      record_data += self.suffix(rtype)

    session_content = "layout: session\n"
    session_content += "permalink: /%s/\n" % record_session
    session_content += "record_data: %s\n" % record_data
    session_content += "record_dir: %s\n" % record_dir

    content = "---\n"
    content += "author: '%s'\n" % info['author'].replace("'", "").split('<')[0].title().rstrip(' ')
    content += "title: '%s'\n" % info['title'].replace("  ", " ").replace("-", " ").replace("'", "").title()
    content += "description: '%s'\n" % info['desc'].replace("'", "")
    content += "category: [%s]\n" % info['category']
    content += "tags: [%s]\n" % info['tags']
    content_end = "---\n"

    # Save record info to markdown, one as session, one as post
    print "LOG:   Generate post markdown"
    f = self.abspath(rec, self.post_md)
    r = open(f,'w+')
    r.write(content + post_content + content_end);
    r.close();

    print "LOG:   Generate session markdown"
    f = self.abspath(rec, self.session_md)
    r = open(f,'w+')
    r.write(content + session_content + content_end);
    r.close();

  def generate_zb64(self, rec, info, rtype = ''):
    data = info['data']
    if rtype == '': rtype = self.zb64

    orig = self.slice_str.join(data)
    info["data_size"] = len(orig)

    out = base64.b64encode(zlib.compress(orig, self.compress_level))
    info["data_compressed"] = out;

    in_size = len(repr(data))
    out_size = len(out)
    ratio = out_size*100 / in_size
    print "LOG:   Compress Ratio: %d%% (%d --> %d)" % (ratio, in_size, out_size)

    info['size'] = self.get_size_unit(out_size)

    zb_content = ""

    # .nvs.x
    if rtype.find(self.slices) >= 0:
      zb_content += "var VNC_frame_size = '%s';\n" % info["size"]
      zb_content += "var VNC_frame_data_size = %s;\n" % info["data_size"]
    # .nvs and .nvz
    else:
      for (k, v) in info.items():
        if k in ("slices", "data", "data_compressed"): continue
        if str(v).isdigit():
          zb_content += "var VNC_frame_%s = %s;\n" % (k, v)
        else:
          zb_content += "var VNC_frame_%s = '%s';\n" % (k, v)

    zb_content += "var VNC_frame_data_compressed = '%s';\n" % info["data_compressed"]

    f = self.abspath(rec, rtype)
    z = open(f, 'w+')
    z.write(zb_content)
    z.close()

    return out_size;

  def generate_slices(self, rec, info, slices):
    slice_index = 0
    slice_frame_start = 0
    slice_frame_end = 0
    slice_frame_length = info['length'] / slices;

    slice_content = ""
    for (k, v) in info.items():
      if k in ("data", "slices", "data_size", "data_compressed"): continue
      if str(v).isdigit():
        slice_content += "var VNC_frame_%s = %s;\n" % (k, v)
      else:
        slice_content += "var VNC_frame_%s = '%s';\n" % (k, v)

    data = info['data']

    while (slice_frame_end < info['length']):
      _slice_frame_length = slice_frame_length
      if slice_index == 0:
        if slice_frame_length < self.min_frames:
          _slice_frame_length = self.min_frames
        if slice_frame_length > self.max_frames:
          _slice_frame_length = self.max_frames

      slice_frame_end = slice_frame_start + _slice_frame_length - 1
      if (slice_frame_end > info['length']):
        slice_frame_end = info['length']
      #elif ((info['length'] - slice_frame_end) < self.min_frames):
      #  slice_frame_end = info['length']

      print "LOG:   start: %d end: %d step: %d _end: %d" % (slice_frame_start, slice_frame_end, _slice_frame_length, info['length'])

      info['data'] = data[slice_frame_start:slice_frame_end]
      self.generate_zb64(rec, info, self.slices + "%d" % slice_index)

      slice_frame_start = slice_frame_end
      slice_index += 1

    print "LOG:   Total: %d, slices: %d" % (info['length'], slice_index)
    info['slices'] = slice_index
    slice_content += "var VNC_frame_%s = %d;\n" % ('slices', info['slices'])

    # Write slice index
    f = self.abspath(rec, self.slice)
    s = open(f, 'w+')
    s.write(slice_content)
    s.close()

    return slice_index

  def get_size_unit(self, size):
    unit = ""
    if size > 1024:
      size = round(size / 1024.0, 1)
      unit = "K"
    if size > 1024:
      size = round(size / 1024.0, 1)
      unit = "M"
    if size > 1024:
      size = round(size / 1024.0, 1)
      unit = "G"
    return str(size) + unit

  def get_frame_time(self, frame):
    t = '00:00:00'
    m = re.match(r'[{}]([0-9]{1,})[{}]', frame)
    if m and len(m.groups()):
      t = self.format_ctime(float(m.group(1))/1000, "%H:%M:%S")

    return t

  def generate_raw(self, zb64):
    info = self.get_frame_info(zb64, self.zb64)
    if not info:
      print "LOG:   Invalid zb64 data"
      return

    raw_content = ''
    for (k, v) in info.items():
      if k in ('data', 'size', 'slice_str', 'slices', 'data_size', 'data_compressed'): continue
      if str(v).isdigit():
        raw_content += "var VNC_frame_%s = %s;\n" % (k, v)
      else:
        raw_content += "var VNC_frame_%s = '%s';\n" % (k, v)

    raw_content += "var VNC_frame_%s = %s;\n" % ('data', ("%r" % info['data']).replace("', '", "',\n'").replace("['{","[\n'{"))

    # Write raw session data
    f = self.abspath(zb64.replace(self.suffix(self.zb64), ''))
    s = open(f, 'w+')
    s.write(raw_content)
    s.close()

  def init_frame_info(self):
    info = {"create": '', "title": '', 'author': '', 'category': '', 'tags': '', 'desc': '', 'encoding': 'binary',
      'length': 0, 'time': 0, 'data': '',
      'size': '', 'slice_str': self.slice_str, 'slices': 0, 'data_size': 0, 'data': '', 'data_compressed': ''}
    return info

  def get_frame_info(self, rec, rtype):
    info = self.init_frame_info()

    for (k, v) in info.items():
      if k in ('encoding', 'data', 'data_compressed'): continue
      exec("VNC_frame_%s = ''" % k)

    f = self.abspath(rec)
    t = open(f)
    py_data = t.read().replace('var VNC_', 'VNC_')
    t.close()

    # Convert origin novnc session record data (javascript) to python code
    exec(py_data)

    key = 'VNC_frame_encoding'
    if not (globals().has_key(key) or locals().has_key(key)):
      # already compressed data, ignore it.
      print "LOG:   Invalid noVNC session data: %s" % rec
      return ''

    if rtype == 'raw':
      key = 'VNC_frame_data'
      if globals().has_key(key) or locals().has_key(key):
        VNC_frame_length = len(VNC_frame_data)
        VNC_frame_time = self.get_frame_time(VNC_frame_data[VNC_frame_length-2])
        VNC_frame_data_compressed = ''
      else: return ''
    elif rtype == self.zb64:
      key = 'VNC_frame_data_compressed'
      if globals().has_key(key) or locals().has_key(key):
        VNC_frame_data = zlib.decompress(base64.b64decode(VNC_frame_data_compressed)).split(self.slice_str)
      else: return ''
    else:
        VNC_frame_data_compressed = ''
        VNC_frame_data = ''

    for (k, v) in info.items():
      val = eval("VNC_frame_%s" % k)
      if val: info[k] = val

    if not info['create']: info['create'] = "%r" % os.path.getctime(f)
    if not info['title']: info["title"] = os.path.basename(rec.replace(self.suffix(self.zb64), ''))
    if not info['author']: info['author'] = "Unknown"
    if not info['category']: info['category'] = ""
    if not info['tags']: info['tags'] = ""
    if not info['desc']: info['desc'] = ""

    # Get file size
    if not info['size']:
      info['size'] = self.get_size_unit(os.path.getsize(f))

    return info

  def generate_list(self, info_list):
    def compare(x, y):
      ctime_x = float(x[4])
      ctime_y = float(y[4])
      if (ctime_x > ctime_y):
        return -1
      elif (ctime_x < ctime_y):
        return 1
      else:
        return 0

    info_list.sort(compare)
    info_list.insert(0, ['Name', 'Title', 'Size', 'Time', 'Create', 'Author', 'Category', 'Tags', 'Desc', 'Slices'])

    content = "var VNC_slice_size = '%s';\n" % self.get_size_unit(self.slice_size)
    content += "var VNC_record_player = '%s';\n" % self.novnc_player
    content += "var VNC_record_dir = '/%s';\n\n" % os.path.basename(self.record_dir.strip('/'))
    content += "var VNC_record_data = "
    content += ("%r" % info_list).replace("], ['", "],\n['").replace("[['","[\n['").decode('string_escape')
    content += ";"

    # Save records list to self.record_list, by default, records.js
    r = open(self.abspath(self.record_list),'w+')
    r.write(content);
    r.close();

  def rec_list(self):
    def compare(x, y):
      stat_x = os.stat(self.abspath(x))
      stat_y = os.stat(self.abspath(y))
      if (stat_x.st_ctime > stat_y.st_ctime):
        return -1
      elif (stat_x.st_ctime > stat_y.st_ctime):
        return 1
      else:
        return 0

    rec_list = []
    for d in [x[0] for x in os.walk(self.abspath())]:
      d = './' + d.replace(self.record_dir, '') 
      rec_list += [(d + "/" + y).replace('//', '/').replace('./', '') for y in os.listdir(self.abspath(d))]
    rec_list.sort(compare)

    ignores = []
    for rec in rec_list:
      rec_long = self.abspath(rec)
      if not os.path.isfile(rec_long) \
        or rec.find(".gitignore") >= 0 \
        or rec.find(".vnc") >= 0 \
        or rec.find(".git") >= 0 \
        or rec.find(".mp3") >= 0 \
        or os.path.basename(rec) in (self.record_list, self.record_html):
        ignores.append(rec)

    for i in ignores: rec_list.remove(i)

    return rec_list

  def restore_raw(self):
    for rec in self.rec_list():
      if rec.find(".md") >= 0: continue
      if rec.find(self.suffix(self.zb64)) >= 0:
        raw_rec = rec.replace(self.suffix(self.zb64), '')
        if not os.path.exists(self.abspath(raw_rec)):
          print "LOG: Restore %s" % raw_rec
          self.generate_raw(rec)

  def remove_old(self):
    # list and sort by time
    for rec in self.rec_list():
      f = self.abspath(rec)
      if rec.find(".md") >= 0:
        os.remove(f)
        continue
      if rec in (self.record_list, self.record_html) or rec.find(self.suffix(self.slice)) >= 0:
        print "LOG: Remove %s" % rec
        os.remove(f)
      if rec.find(self.suffix(self.zb64)) >= 0:
        raw_rec = rec.replace(self.suffix(self.zb64), '')
        if os.path.exists(self.abspath(raw_rec)):
          print "LOG: Remove %s" % rec
          os.remove(f)
        elif 'restore_raw' in self.action:
          print "LOG: Restore %s" % raw_rec
          self.generate_raw(rec)
          #print "LOG: Remove %s" % rec
          #os.remove(f)

  def generate(self):
    # Remove old record list, .nvz and .nvs*
    if 'remove' in self.action:
      self.remove_old()

    if 'restore_raw' in self.action:
      self.restore_raw()

    if 'zb64' not in self.action and 'slice' not in self.action:
      return

    # Grab the records info and generate files with zlib+base64 and if the
    # file is too big, slice it to several pieces.
    info_list = []
    for rec in self.rec_list():
      # Ignore some files
      print "LOG: " + rec

      rtype = 'raw'
      if rec.find(".md") >= 0: continue
      if rec.find(self.suffix(self.slice)) >= 0:
        if rec.find(self.suffix(self.slice) + ".") >= 0: continue
        rtype = self.slice
      if rec.find(self.suffix(self.zb64)) >= 0 and rec.find(self.suffix(self.slice)) < 0:
        rtype = self.zb64
        if os.path.exists(self.abspath(rec.replace(self.suffix(rtype), ''))): continue

      # Grab frame info
      info = self.get_frame_info(rec, rtype)
      if not info: continue

      if rtype == self.slice:
        found = 0
        for ri in info_list:
          if info['title'] == ri[1] and info['create'] == ri[4] and info['time'] == ri[3]:
            found = 1
            break
        if found:
          continue

        rec_name = rec.replace(self.record_dir, '')
        info_list.append([rec_name, os.path.basename(info['title']), info['size'], info['time'],
                       info['create'], info['author'], info['category'], info['tags'],
                       info['desc'], 1])
        if 'md' in self.action:
          rec = rec.replace(self.suffix(self.slice), '')
          self.generate_markdown(rec, info, self.slice)
        continue

      # Generate xxx.nvz
      if rtype == self.raw:
        f = self.abspath(rec, self.zb64)
      if rtype == self.zb64:
        f = self.abspath(rec)

      found = 0
      for ri in info_list:
        if info['title'] == ri[1] and info['create'] == ri[4] and info['time'] == ri[3]:
          found = 1
          break
      if found:
        print "LOG:   Already exists, Ignore it"
        continue

      out_size = 0
      if not os.path.exists(f):
        if 'zb64' in self.action:
          print "LOG:   Generate zb64"
          out_size = self.generate_zb64(rec, info)
          if 'md_default' in self.action:
            self.generate_markdown(rec, info, self.zb64)
      else:
        out_size = os.path.getsize(f)
        if 'md' in self.action:
          self.generate_markdown(rec, info, self.zb64)

      # Generate xxx.nvs
      if rtype == self.zb64:
        rec = rec.replace(self.suffix(rtype), '')

      size = info['size'] = self.get_size_unit(out_size)
      slices = 0
      #if out_size and out_size > self.slice_size and 'slice' in self.action:
      if 'slice' in self.action:
        if not os.path.exists(self.abspath(rec, self.slice)):
          print "LOG:   Generate slices"
          slices = out_size / self.slice_size + 1
          slices = self.generate_slices(rec, info, slices)
          if 'md_default' in self.action:
            self.generate_markdown(rec, info, self.slice)
        elif 'md' in self.action:
          self.generate_markdown(rec, info, self.slice)

      if slices == 0:
        slice_file = self.abspath(rec + self.suffix(self.slice))
        if os.path.exists(slice_file): slices = 1

      if slices:
         slices = 1
         rec_name = self.abspath(rec, self.slice)
      else:
         rec_name = self.abspath(rec, self.zb64)

      rec_name = rec_name.replace(self.record_dir, '')
      info_list.append([rec_name, os.path.basename(info['title']), size, info['time'],
                       info['create'], info['author'], info['category'], info['tags'],
                       info['desc'], slices])

      # Remove raw data, save the space
      if 'remove_raw' in self.action:
        f = self.abspath(rec)
        if os.path.exists(f):
          zb64 = self.abspath(rec + self.suffix(self.zb64))
          if not os.path.exists(zb64):
            print "LOG:   .zb64 doesn't exist, not remove raw data for security"
          else:
            print "LOG:   Remove raw data"
            os.remove(f)

    # Generate list
    if not info_list: return
    print "LOG: Generate %s" % self.record_list
    self.generate_list(info_list)
