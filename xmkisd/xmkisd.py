import argparse
import sys
import os
import glob
import shutil

from PIL import Image

#
#  pcm to adpcm converter class
#
class ADPCM:

  step_adjust = [ -1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8 ]

  step_size = [  16,  17,  19,  21,  23,  25,  28,  31,  34,  37,  41,  45,   50,   55,   60,   66,
                 73,  80,  88,  97, 107, 118, 130, 143, 157, 173, 190, 209,  230,  253,  279,  307,
                337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552 ]


  def decode_adpcm(self, code, step_index, last_data):

    ss = ADPCM.step_size[ step_index ]

    delta = ( ss >> 3 )

    if code & 0x01:
      delta += ( ss >> 2 )

    if code & 0x02:
      delta += ( ss >> 1 )

    if code & 0x04:
      delta += ss

    if code & 0x08:
      delta = -delta
      
    estimate = last_data + delta

    if estimate > 2047:
      estimate = 2047

    if estimate < -2048:
      estimate = -2048

    step_index += ADPCM.step_adjust[ code ]

    if step_index < 0:
      step_index = 0

    if step_index > 48:
      step_index = 48

    return (estimate, step_index)


  def encode_adpcm(self, current_data, last_estimate, step_index):

    ss = ADPCM.step_size[ step_index ]

    delta = current_data - last_estimate

    code = 0x00
    if delta < 0:
      code = 0x08         # bit3 = 1
      delta = -delta

    if delta >= ss:
      code += 0x04        # bit2 = 1
      delta -= ss

    if delta >= ( ss >> 1 ):
      code += 0x02        # bit1 = 1
      delta -= ss>>1

    if delta >= ( ss >> 2 ):
      code += 0x01        # bit0 = 1
      
    # need to use decoder to estimate
    (estimate, adjusted_index) = self.decode_adpcm(code, step_index, last_estimate)

    return (code,estimate, adjusted_index)


  def convert_pcm_to_adpcm(self, pcm_file, pcm_freq, pcm_channels, adpcm_file, adpcm_freq, max_peak, min_avg):

    rc = 1

    with open(pcm_file, "rb") as pf:

      pcm_bytes = pf.read()
      pcm_data = []

      pcm_peak = 0
      pcm_total = 0.0
      num_samples = 0

      resample_counter = 0

      if pcm_channels == 2:
        for i in range(len(pcm_bytes) // 4):
          resample_counter += adpcm_freq
          if resample_counter >= pcm_freq:
            lch = int.from_bytes(pcm_bytes[i*4+0:i*4+2], 'big', signed=True)
            rch = int.from_bytes(pcm_bytes[i*4+2:i*4+4], 'big', signed=True)
            pcm_data.append((lch + rch) // 2)
            resample_counter -= pcm_freq
            if abs(lch) > pcm_peak:
              pcm_peak = abs(lch)
            if abs(rch) > pcm_peak:
              pcm_peak = abs(rch)
            pcm_total += float(abs(lch) + abs(rch))
            num_samples += 2
      else:
        for i in range(len(pcm_bytes) // 2):
          resample_counter += adpcm_freq
          if resample_counter >= pcm_freq:
            mch = int.from_bytes(pcm_bytes[i*2+0:i*2+2], 'big', signed=True)
            pcm_data.append(mch)
            resample_counter -= pcm_freq
            if abs(mch) > pcm_peak:
              pcm_peak = abs(mch)
            pcm_total += float(abs(mch))
            num_samples += 1

      avg_level = 100.0 * pcm_total / num_samples / 32767.0
      peak_level = 100.0 * pcm_peak / 32767.0
      print(f"Average Level ... {avg_level:.2f}%")
      print(f"Peak Level    ... {peak_level:.2f}%")

      if avg_level < float(min_avg) or peak_level > float(max_peak):
        print("Level range error. Adjust volume settings.")
        return 1

      last_estimate = 0
      step_index = 0
      adpcm_data = []

      for i,x in enumerate(pcm_data):

        # signed 16bit to 12bit, then encode to ADPCM
        xx = x // 16
        (code, estimate, adjusted_index) = self.encode_adpcm(xx, last_estimate, step_index) 

        # fill a byte in this order: lower 4 bit -> upper 4 bit
        if i % 2 == 0:
          adpcm_data.append(code)
        else:
          adpcm_data[-1] |= code << 4

        last_estimate = estimate
        step_index = adjusted_index

      with open(adpcm_file, 'wb') as af:
        af.write(bytes(adpcm_data))

    return 0

  def check_pcm_level(self, pcm_file, pcm_freq, pcm_channels, max_peak, min_avg):

    rc = 1

    with open(pcm_file, "rb") as pf:

      pcm_bytes = pf.read()

      pcm_peak = 0
      pcm_total = 0.0
      num_samples = 0

      if pcm_channels == 2:
        for i in range(len(pcm_bytes) // 4):
          lch = int.from_bytes(pcm_bytes[i*4+0:i*4+2], 'big', signed=True)
          rch = int.from_bytes(pcm_bytes[i*4+2:i*4+4], 'big', signed=True)
          if abs(lch) > pcm_peak:
            pcm_peak = abs(lch)
          if abs(rch) > pcm_peak:
            pcm_peak = abs(rch)
          pcm_total += float(abs(lch) + abs(rch))
          num_samples += 2
      else:
        for i in range(len(pcm_bytes) // 2):
          mch = int.from_bytes(pcm_bytes[i*2+0:i*2+2], 'big', signed=True)
          if abs(mch) > pcm_peak:
            pcm_peak = abs(mch)
          pcm_total += float(abs(mch))
          num_samples += 1

      avg_level = 100.0 * pcm_total / num_samples / 32767.0
      peak_level = 100.0 * pcm_peak / 32767.0
      print(f"Average Level ... {avg_level:.2f}%")
      print(f"Peak Level    ... {peak_level:.2f}%")

      if avg_level < float(min_avg) or peak_level > float(max_peak):
        print("Level range error. Adjust volume settings.")
        return 1

    return 0

#
#  bmp/pcm to isd converter class
#
class BMPtoISD:
 
  def convert(self, output_file, src_image_dir, view_width, view_height, use_ibit, fps, square_mode, \
              pcm_freq, pcm_wip_file, adpcm_wip_file, comment):

    rc = 0

    frame0 = False

    with open(output_file, "wb") as f:

      pcm_data = None
      if pcm_freq == 15625:
        with open(adpcm_wip_file, "rb") as af:
          pcm_data = af.read()
      else:
        with open(pcm_wip_file, "rb") as pf:
          pcm_data = pf.read()

      bmp_files = sorted(os.listdir(src_image_dir))
      num_frames = len(bmp_files)
      written_frames = 0

      screen_width = 384 if square_mode else 256
      screen_height = 256
      ofs_x = ( screen_width - view_width ) // 2
      ofs_y = ( screen_height - view_height ) // 2

      if pcm_freq == 15625:
        if fps == 18:
          frame_voice_size = 7812 // fps
        elif fps == 22 or fps == 27.5:
          frame_voice_size = 7810 // fps
        else:
          frame_voice_size = 7800 // fps
      elif pcm_freq == 22050:
        if fps == 22:
          frame_voice_size = 22044 // fps * 4
        elif fps == 27.5:
          frame_voice_size = 22055 // fps * 4
        else:
          frame_voice_size = pcm_freq * 4 // fps
      elif pcm_freq == 24000:
        if fps == 18:
          frame_voice_size = 24012 // fps * 4
        elif fps == 22:
          frame_voice_size = 24002 // fps * 4
        elif fps == 27.5:
          frame_voice_size = 23980 // fps * 4
        else:
          frame_voice_size = pcm_freq * 4 // fps
      elif pcm_freq == 32000:
        if fps == 6 or fps == 12 or fps == 18 or fps == 24:
          frame_voice_size = 64008 // fps * 2     # 24fps
        elif fps == 15 or fps == 30:
          frame_voice_size = 63990 // fps * 2     # 15/30fps
        elif fps == 22:
          frame_voice_size = 63998 // fps * 2
        elif fps == 27.5:
          frame_voice_size = 64020 // fps * 2
        else:
          frame_voice_size = 64000 // fps * 2     # 10/20fps
      elif pcm_freq == 44100:
        if fps == 22 or fps == 27.5:
          frame_voice_size = 44110 // fps * 4
        else:
          frame_voice_size = pcm_freq * 4 // fps
      elif pcm_freq == 48000:
        if fps == 18:
          frame_voice_size = 48006 // fps * 4
        elif fps == 22:
          frame_voice_size = 48004 // fps * 4
        elif fps == 27.5:
          frame_voice_size = 48015 // fps * 4
        else:
          frame_voice_size = pcm_freq * 4 // fps

      frame_size = ( 1 + ( view_width * view_height * 2 + frame_voice_size ) // 1024 ) * 1024
      header_size = 1024

      written_pcm_size = 0

      pcm_rate_type = 0x403       # ADPCM 15.6kHz
      if pcm_freq == 22050:       # S22
        pcm_rate_type = 0b00101111
      elif pcm_freq == 24000:     # S24
        pcm_rate_type = 0b00111111
      elif pcm_freq == 32000:     # S32
        pcm_rate_type = 0b10011111
      elif pcm_freq == 44100:     # S44
        pcm_rate_type = 0b10101111
      elif pcm_freq == 48000:     # S48
        pcm_rate_type = 0b10111111

      if pcm_freq == 15625:
        f.write("ISPR-V3.0\x00".encode('ascii'))
      else:
        f.write("ISPR-V4.0\x00".encode('ascii'))
      f.write(view_width.to_bytes(4, 'big'))
      f.write(view_height.to_bytes(4, 'big'))
      if fps == 22 or fps == 24 or fps == 27.5:
        f.write((60 // 30).to_bytes(4, 'big'))
        f.write((60 // 20).to_bytes(4, 'big'))
      elif fps == 18:
        f.write((60 // 20).to_bytes(4, 'big'))
        f.write((60 // 15).to_bytes(4, 'big'))        
      else:
        f.write((60 // fps).to_bytes(4, 'big'))
        f.write((60 // fps).to_bytes(4, 'big'))
      f.write(pcm_rate_type.to_bytes(4, 'big'))
      f.write(frame_size.to_bytes(4, 'big'))
      f.write(header_size.to_bytes(4, 'big'))

      comment_bytes = f"CM{comment}\x00".encode('cp932', errors='ignore')
      f.write(comment_bytes)
      f.write(bytes([0] * (1024 - 38 - len(comment_bytes))))

      for i, bmp_name in enumerate(bmp_files):

        if bmp_name.lower().endswith(".bmp"):

          im = Image.open(src_image_dir + os.sep + bmp_name)

          im_width, im_height = im.size
          if im_width != view_width:
            print("error: bmp width is not same as view width.")
            return rc

          im_bytes = im.tobytes()

          grm_bytes = bytearray(view_width * view_height * 2)
          for y in range(im_height):
            for x in range(im_width):
              r = im_bytes[ (y * im_width + x) * 3 + 0 ] >> 3
              g = im_bytes[ (y * im_width + x) * 3 + 1 ] >> 3
              b = im_bytes[ (y * im_width + x) * 3 + 2 ] >> 3
              c = (g << 11) | (r << 6) | (b << 1)
              if use_ibit:
                ge = im_bytes[ (y * im_width + x) * 3 + 1 ] % 8
                if ge >= 4:
                  c += 1
              else:
                if c > 0:
                  c += 1
              grm_bytes[ y * view_width * 2 + x * 2 + 0 ] = c // 256
              grm_bytes[ y * view_width * 2 + x * 2 + 1 ] = c % 256

          gvram_addr = 0xC00000 + ofs_y * 512 * 2 + ofs_x * 2
          y_delta = 512 * 2
          y_copy = 0
          f.write(gvram_addr.to_bytes(4, 'big'))
          f.write(view_width.to_bytes(2, 'big'))
          f.write(view_height.to_bytes(2, 'big'))
          f.write(y_delta.to_bytes(4, 'big'))
          f.write(y_copy.to_bytes(4, 'big'))
          f.write(grm_bytes)
          f.write(frame_voice_size.to_bytes(2, 'big'))
          f.write(pcm_data[written_pcm_size : written_pcm_size + frame_voice_size])
          f.write(bytes([0] * (frame_size - 16 - len(grm_bytes) - 2 - frame_voice_size)))
          written_frames += 1
          written_pcm_size += frame_voice_size
          print(".", end="", flush=True)

      if written_frames == len(bmp_files):
        rc = 0

    print()

    return rc

#
#  stage 1 mov to adpcm/pcm
#
def stage1(src_file, src_cut_ofs, src_cut_len, \
           pcm_volume, pcm_peak_max, pcm_avg_min, pcm_freq, pcm_wip_file, adpcm_wip_file):

  print("[STAGE 1] started.")

  opt = f"-y -i {src_file} "

  if pcm_freq == 15625:
    opt += f"-f s16be -acodec pcm_s16be -filter:a \"volume={pcm_volume},lowpass=f={pcm_freq}\" -ar {pcm_freq} -ac 1 -ss {src_cut_ofs} -t {src_cut_len} {pcm_wip_file} "
  else:
    opt += f"-f s16be -acodec pcm_s16be -filter:a \"volume={pcm_volume}\" -ar {pcm_freq} -ac 2 -ss {src_cut_ofs} -t {src_cut_len} {pcm_wip_file} "
  
  if os.system(f"ffmpeg {opt}") != 0:
    print("error: ffmpeg failed.")
    return 1
  
  if pcm_freq == 15625:
    if ADPCM().convert_pcm_to_adpcm(pcm_wip_file, pcm_freq, 1, adpcm_wip_file, pcm_freq, pcm_peak_max, pcm_avg_min) != 0:
      print("error: adpcm conversion failed.")
      return 1
  else:
    if ADPCM().check_pcm_level(pcm_wip_file, pcm_freq, 2, pcm_peak_max, pcm_avg_min) != 0:
      print("error: pcm level check failed.")
      return 1
  
  print("[STAGE 1] completed.")

  return 0

#
#  stage2 mov to bmp
#
def stage2(src_file, src_cut_ofs, src_cut_len, fps, square_mode, view_width, view_height, deband, sharpness, output_bmp_dir):

  print("[STAGE 2] started.")

  if view_width % 8 != 0:
    print("error: view_width must be 8 * n")
    return 1

  if view_width < 128:
    print("error: view_width is too small.")
    return 1

  if square_mode is False and view_width > 256:
    print("error: view_width is too large.")
    return 1

  if square_mode and view_width > 384:
    print("error: view_width is too large.")
    return 1

  if view_height > 256:
    print("error: view_height is too large.")
    return 1

  os.makedirs(output_bmp_dir, exist_ok=True)

  for p in glob.glob(f"{output_bmp_dir}{os.sep}*.bmp"):
    if os.path.isfile(p):
      os.remove(p)

  if sharpness > 0.0:
    sharpness_filter=f",unsharp=3:3:{sharpness}:3:3:0"
  else:
    sharpness_filter=""
  
  if deband:
    deband_filter=",deband=1thr=0.02:2thr=0.02:3thr=0.02:blur=1"
    deband_filter2="-pix_fmt rgb565"
  else:
    deband_filter=""
    deband_filter2=""

  opt = f"-y -i {src_file} -ss {src_cut_ofs} -t {src_cut_len} " + \
        f"-filter_complex \"[0:v] fps={fps},scale={view_width}:{view_height}{sharpness_filter}{deband_filter}\" " + \
        f"-vcodec bmp {deband_filter2} \"{output_bmp_dir}/output_%05d.bmp\""

  if os.system(f"ffmpeg {opt}") != 0:
    print("error: ffmpeg failed.")
    return 1
  
  print("[STAGE 2] completed.")

  return 0

#
#  stage 3 bmp/pcm to isd
#
def stage3(output_bmp_dir, view_width, view_height, use_ibit, fps, square_mode, pcm_freq, pcm_wip_file, adpcm_wip_file, comment, isd_data_file):

  print("[STAGE 3] started.")

  if BMPtoISD().convert(isd_data_file, output_bmp_dir, view_width, view_height, use_ibit, fps, square_mode, pcm_freq, pcm_wip_file, adpcm_wip_file, comment) != 0:
    print("error: BMP/PCM to ISD conversion failed.")
    return 1
  
  print("[STAGE 3] completed.")

  return 0

#
#  main
#
def main():

  parser = argparse.ArgumentParser()
  parser.add_argument("src_file", help="source movie file")
  parser.add_argument("isd_name", help="target isd name")
  parser.add_argument("-fps", help="frame per second", type=float, default=15, choices=[6,10,12,15,18,20,22,24,27.5,30])
  parser.add_argument("-co", "--src_cut_ofs", help="source cut start offset", default="00:00:00.000")
  parser.add_argument("-cl", "--src_cut_len", help="source cut length", default="01:00:00.000")
  parser.add_argument("-vw", "--view_width", help="view width", type=int, default=216)
  parser.add_argument("-vh", "--view_height", help="view height", type=int, default=168)
  parser.add_argument("-sq", "--square_mode", help="square pixel mode", action='store_true')
  parser.add_argument("-pv", "--pcm_volume", help="pcm volume", type=float, default=1.0)
  parser.add_argument("-pp", "--pcm_peak_max", help="pcm peak max", type=float, default=98.5)
  parser.add_argument("-pa", "--pcm_avg_min", help="pcm average min", type=float, default=8.0)
  parser.add_argument("-pf", "--pcm_freq", help="pcm frequency", type=int, default=15625, choices=[15625, 22050, 24000, 32000, 44100, 48000])
  parser.add_argument("-ib", "--use_ibit", help="use i bit for color reduction", action='store_true')
  parser.add_argument("-db", "--deband", help="use debanding filter", action='store_true')
  parser.add_argument("-sp", "--sharpness", help="sharpness (max 1.5)", type=float, default=0.6)
  parser.add_argument("-cm", "--comment", help="comment", default="build with xmkisd")
  parser.add_argument("-bm", "--preserve_bmp", help="preserve output bmp folder", action='store_true')

  args = parser.parse_args()

  output_bmp_dir = "output_bmp"

  isd_data_file = f"{args.isd_name}"
  if isd_data_file[-4:].upper() not in [".ISD", ".ISM", ".ISS"]: 
    if args.square_mode:
      isd_data_file += ".ISS"
    elif args.pcm_freq == 15625:
      isd_data_file += ".ISD"
    else:
      isd_data_file += ".ISM"

  pcm_wip_file = f"_wip_pcm.dat"
  adpcm_wip_file = f"_wip_adpcm.dat" if args.pcm_freq == 15625 else None

  if stage1(args.src_file, args.src_cut_ofs, args.src_cut_len, \
            args.pcm_volume, args.pcm_peak_max, args.pcm_avg_min, args.pcm_freq, pcm_wip_file, adpcm_wip_file) != 0:
    return 1
  
  if stage2(args.src_file, args.src_cut_ofs, args.src_cut_len, \
            args.fps, args.square_mode, args.view_width, args.view_height, args.deband, args.sharpness, \
            output_bmp_dir) != 0:
    return 1

  if stage3(output_bmp_dir, args.view_width, args.view_height, args.use_ibit, args.fps, args.square_mode, \
            args.pcm_freq, pcm_wip_file, adpcm_wip_file, args.comment, isd_data_file):
    return 1

  if pcm_wip_file:
    if os.path.isfile(pcm_wip_file):
	    os.remove(pcm_wip_file)

  if adpcm_wip_file:
    if os.path.isfile(adpcm_wip_file):
      os.remove(adpcm_wip_file)

  if args.preserve_bmp is False:
    shutil.rmtree(output_bmp_dir, ignore_errors=True)

  return 0

if __name__ == "__main__":
  main()
