from rtlsdr import RtlSdr
from scipy import signal
import numpy as np
import threading
import queue
import pyaudio
 
sdr = RtlSdr()
samples = queue.Queue()
sounds = queue.Queue()
 

audio_rate = 40000 # sample rate for sound card
audio_output = pyaudio.PyAudio().open(format=pyaudio.paInt16, channels=1, rate=audio_rate, output=True)
global Fs 
Fs = 1140000


class readThread (threading.Thread):
   def __init__(self, sdr, samples):
      threading.Thread.__init__(self)
      self.srd = sdr
      self.samples = samples
      self.TurnOff = False


   def run(self):
        print ("taking samples")
        while not self.TurnOff:
            self.samples.put(sdr.read_samples(1802000))

 
class processThread (threading.Thread):
    def __init__(self, samples, sounds):

        threading.Thread.__init__(self)
        self.samples = samples
        self.sounds = sounds
        self.TurnOff = False

    def run(self):
        while not self.TurnOff:
            print('processing')
            global Fs
            # taking samples stored in queue
            samples = self.samples.get()
            samples = np.array(samples).astype("complex64") #converting to numpy array

         
            f_bw = 205000  # bandwidth FM in Hz
            dec_fac = int(Fs / f_bw)  # calculating the decimation factor
            samples = signal.decimate(samples, dec_fac) # downsample the signal by a factor = dec_fac

            Fs_new = Fs/dec_fac  # calculating the new sampling rate

            angle = np.angle(samples) # angle = numpy array containing the angles of the complex samples in rad
            correct_angle = np.unwrap(angle) # remove phase jumps
            samples = np.diff(correct_angle) # np.diff ==> takes the difference between the elements

            cutoff= 15e3 # cut-off frequency
            
            b, a = signal.butter(5, cutoff/ (Fs_new / 2), 'lowpass')
            # 5 = order ==> for the transition
            # cutoff/ (Fs / 2) ==> normalized cut-off frequency
            # returns coeff of the transfer function (function that describes the behavior of the filter)

            samples = signal.filtfilt(b, a, samples) # function that applies the filter on the samples (original shape of the waveform is preserved)
                                                     # result is the mono audio part of the signal
            
            
            #b, a = signal.butter(5, 100 / (Fs_new / 2), 'highpass')
            #samples = signal.filtfilt(b, a, samples)

            # decimating once again to get a sample rate for the sound card
            audio_freq = 40000.0 
            dec_audio = int(Fs_new/audio_freq)  
            audio = signal.decimate(samples, dec_audio) 

            # scaling audio for the volume
            audio *= 1000 / np.max(np.abs(audio))  
            self.sounds.put(audio) # storing audio in the sounds queue
         

# configuring the device
sdr.sample_rate = Fs 
sdr.center_freq = 98.8e6
sdr.gain = 30
Fs_audio = 0


thread1 = readThread(sdr, samples)
thread2 = processThread(samples, sounds)
thread1.start()
thread2.start()

try:
    while True:
        audio = sounds.get() # getting audio stored in sounds queue
        print('playing...')
        audio_output.write(audio.astype("int16").tobytes()) # play the audio
except KeyboardInterrupt:
    print("bye")
    thread1.TurnOff = True
    thread2.TurnOff = True
    # stop broadcasting