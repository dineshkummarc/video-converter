#!/usr/bin/env python

"""
Video converter utilites wrappers collection
"""
# -*- coding: utf-8 -*- 

import subprocess
import os
import sys
import re
import math


__all__ = ['escape_shell_arg', 'require_utility', 'get_video_data', 
           'make_snapshot', 'inject_metadata']


def escape_shell_arg(arg):
    """
    Escape a string to be used as a shell argument

    Adds single quotes around a string and quotes/escapes
    any existing single quotes allowing you to pass a string directly to a
    shell function and having it be treated as a single safe argument.

    This function should be used to escape individual arguments to shell
    functions coming from user input. 

    `arg` - The argument that will be escaped.
    """
    return '\'' + arg.replace('\'', '\'' + '\\' + '\'' + '\'') + '\''


def check_utility(command):
    """
    Checks that `command` utility is exists and can be called.

    This function makes pipe call with `command` with '--help' argument. If
    this call raises OSError, we guess `command` not installed. 
    """
    try:
        subprocess.check_call([command, '--help'], 
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
        )
    except OSError, e:
        raise UtilityNotFound, 'Utility %s not found' % command
    except subprocess.CalledProcessError, e:
        pass


def require_utility(*requirements):
    """
    Decorator that checks all required utilities is available
    """
    def wrapper(function):
        """
        Wrap function
        """
        def handler(*args, **kwargs):
            """
            Iterates for requirements and checks it            
            """
            for requirement in requirements:
                check_utility(requirement)
            return function(*args, **kwargs)
        return handler
    return wrapper


def popen(command, handler=None, kwargs={}, miss_count=5):
    """
    Opens the pipe with external utility.

    `command` - shell command that will be created in subprocess.Popen stream
    or shell.

    `handler` (not required) - the callable object that handles each line readed
    from pipe. Handler accepts one required argument: stream line for parsing.
    Other arguments will be passed as keyword arguments.

    `kwargs` (not required) - dictionary with extra arguments that will
    passed to handler as non-required input arguments.

    `miss_count` - number of pipe read errors after that pipe will be closed.

    """
    stream, eof_count = subprocess.Popen(command,
        shell  = True,
        stdout = subprocess.PIPE,
        stderr = subprocess.STDOUT,
        universal_newlines = True
    ).stdout, 0

    while True:
        line = stream.readline()

        # Break infinite loop if EOF exceed
        if len(line) < 1:
            if eof_count > miss_count: break
            else:
                eof_count += 1;
                continue
        else:
            eof_count = 0

        if callable(handler):
            handler(line, **kwargs)


@require_utility('mplayer')
def get_video_metadata(filename):
    """
    Returns a dictionary with video metadata.

    Retrieves all available meta information about movie such as frame width,
    frame height, bitrate, video- and audio codecs, container format,
    duration and so on by `mplayer` command line interface: 
   
       $ mplayer -vo null -ao null -frames 0 -identify `filename`

    It parses `mplayer` stdout and puts data into dictionary. If system shell
    can't execute `mencoder`, the UtilityNotFound exception will
    be raised.

    """
    infomap, metadata = (
        # String marker          # Dictionary key     # Filters sequence
        ('ID_AUDIO_CODEC',       'audio_codec',       [unicode]),
        ('ID_AUDIO_FORMAT',      'audio_format',      [unicode]),
        ('ID_AUDIO_BITRATE',     'audio_bitrate',     [int]),
        ('ID_AUDIO_RATE',        'audio_rate',        [int]),
        ('ID_AUDIO_NCH',         'audio_nch',         [int]),
        ('ID_VIDEO_FORMAT',      'video_format',      [unicode]),
        ('ID_VIDEO_BITRATE',     'video_bitrate',     [int]),
        ('ID_VIDEO_ASPECT',      'video_aspect',      [float]),
        ('ID_VIDEO_WIDTH',       'width',             [int]),
        ('ID_VIDEO_HEIGHT',      'height',            [int]),         
        ('ID_VIDEO_FPS',         'frame_rate',        [float]),
        ('ID_LENGTH',            'duration',          [float, math.ceil, int]),
        ('ID_CLIP_INFO_VALUE0',  'clip_info_value0',  [unicode]),
        ('ID_VIDEO_ID',          'video_id',          [int]),
        ('ID_AUDIO_ID',          'audio_id',          [int]),
        ('ID_CLIP_INFO_N',       'clip_info_n',       [unicode]),
        ('ID_FILENAME',          'filename',          [unicode]),
        ('ID_DEMUXER',           'demuxer',           [unicode]),
        ('ID_SEEKABLE',          'seekable',          [bool]),
        ('ID_CHAPTERS',          'chapters',          [int]),
        ('ID_VIDEO_CODEC',       'video_codec',       [unicode]),
        ('ID_EXIT',              'exit',              [unicode]),
    ), {}

    def line_handler(line, metadata, infomap):
        """
        Stream line parser
        """
        if not line.startswith('ID_'):
            return

        for token, field, filters  in infomap:
            if line.startswith(token):
                key, val = line.strip().split('=', 2)
                for f in filters:
                    val = f(val)
                metadata[field] = val

    # Command for retrieving metadata from video
    command = ' '.join(['mplayer',
        '-vo null',
        '-ao null',
        '-frames 0',
        '-identify',
        escape_shell_arg(filename)]
    )

    # Parse the string
    popen(command, line_handler, kwargs={
        'infomap': infomap,
        'metadata': metadata,
    })

    if len(metadata.keys()) < 2:
        raise WrongVideoFormat, 'Can\'t parse metadata, maybe wrong format'
    return metadata


@require_utility('ffmpeg')
def make_snapshot(video_filename, snapshot_filename, position): 
    """
    Makes a snapshot for `video_filename` at position `position` (in seconds)
    and names it `snapshot_filename`.

    This function is command line interface to ffmpeg utility. It opens such
    shell command in python subprocess.Popen pipe:    

     $ ffmpeg -ss `pos` -i `video` -an -vframes 1 -y -f mjpeg `snapshot`
     
    where `pos` - is position of video (in seconds from start), `video` - is
    input video file, `snapshot` - snapshot filename.

    IMPORTANT! The '-ss' argument must follow first '-i' (input file) 
    argument, in other case ffmpeg will seek given position in whole file
    and thus it can significantly slow process.

    """
    command = ' '.join(['ffmpeg',
        '-ss {position}'.format(position=position),
        '-i  {video}'.format(video=escape_shell_arg(video_filename)),
        '-an -vframes 1 -y -f mjpeg',
        escape_shell_arg(snapshot_filename),
    ])
    popen(command)

    # If snapshot is broken (null length), delete it and returns False
    if not os.path.getsize(snapshot_filename) > 0:
        os.remove(snapshot_filename)
        return False
    return True


@require_utility('yamdi')
def inject_metadata(input_filename, output_filename):
    command = ' '.join(['yamdi',
        '-i {input}'.format(input=escape_shell_arg(input_filename)),
        '-o {output}'.format(output=escape_shell_arg(output_filename)),
        ])
    popen(command)


class UtilityNotFound(Exception):
    """
    Exception that raises when required utility is not found in $PATH
    """


class CodecNotFound(Exception):
    """
    Exception that raises when trying convert video within unknown codec
    """


class WrongCommandLine(Exception):
    """
    Exception that raises when trying convert video within unknown codec
    """


class WrongVideoFormat(Exception):
    """
    Exception that raises when can't retrieve video metadata
    """


class ConvertResult(object):
    """
    Result object
    """
    STATE_SUCCESS = True
    STATE_FAILURE = False

    # Absolute path to source file
    movie_original = ''

    # Absolute path to result file
    movie_converted = ''

    # Success converted flag (mencoder)
    converted = False

    # Movie metadata dictionary
    metadata = {}

    # Converted movie snapshots
    snapshots = {}


class BaseConverter(object):
    """
    Base converter class
    """
    width = 640
    height = 480

    sample_rate = 22050
    output_format = 'lavf'
    video_codec = 'lavc'
    video_opts = None
    video_opts_prefix = ''   
    audio_codec = 'lavc'
    audio_opts = None
    audio_opts_prefix = ''

    def __init__(self, *args, **kwargs):
        """
        The class constructor
        """
        self.width  = kwargs.get('width') or self.width
        self.height = kwargs.get('height') or self.height 

    def convert(self, input_file, output_file, **kwargs):
        """
        Start the converting process 
        """
        result = ConvertResult()
 
        result.movie_original = input_file
        result.movie_info = self.get_movie_info(input_file)
        result.converted = self.encode(input_file, output_file, **kwargs)

        if result.converted:
            result.movie_converted = output_file            
            self.make_snapshot(result)
            self.inject_metadata(output_file)
        return result

    def encode(self, input_file, output_file, **kwargs):
        """
        """
        if hasattr(self, 'parse_converter_output'):
            self.parse_converter_output(input_file, output_file, **kwargs)

        command = self.get_encode_command(input_file, output_file)
        popen(command)

        return True

    def snapshot_filename(self, result, second):
        """
        Returns snapshot filename
        """
        return '{video_file}_{second}.jpeg'.format(
            video_file = result.movie_converted,
            second     = second,
        )

    def make_snapshot(self, result, num=10): 
        """
        Make snapshots
        """
        # Gets movie duration in seconds
        duration = result.movie_info['duration'] 

        # Gets step (in integer seconds) between two snaphots
        step = float(duration / num)
        step = math.floor(step)

        # Gets list of target positions (in seconds)
        seconds = xrange(1, duration - 1, step)
        seconds = list(seconds)
        seconds.append(duration)
        seconds.append(math.floor(float(duration) / 2) )

        for position in seconds:
            position = int(position)

            thumb_filename = self.snapshot_filename(result, position)

            if thumb_filename is None:
                continue

            if make_snapshot(result.movie_converted, thumb_filename, position):
                result.snapshots[position] = thumb_filename

    def get_movie_info(self, input_file):
        """
        Retrieve all metadata such as frame width, height, rate, audio and
        video codecs, duration and so on.
        """
        return get_video_metadata(input_file)

    def inject_metadata(self, output_file):
        """
        Inject metadata into converted movie
        """
        inject_metadata(output_file, output_file + '.yamdi')       
        os.remove(output_file)
        os.rename('%s.yamdi' % output_file, output_file)

    def process_handler(self, old, new):
        ''
        print '%s\t->\t%s' % (old, new)


class MencoderConverter(BaseConverter):
    """
    MEncoder converter base class
    """
    def get_encode_command(self, input_file, output_file):
        """
        Return `mencoder` console command to convert movie
        """
        def input_filename():
            """
            Returns a input filename argument substring
            """
            return escape_shell_arg(input_file)

        def output_filename():
            """
            Returns a output filename (-o) argument substring
            """
            return '-o {output_file}'.format(output_file=output_file)

        def container():
            """
            Returns a output format (-of) argument substring
            """
            return '-of {format}'.format(format=self.output_format)

        def vcodec():
            """
            Returns a video codec (-ovc) argument substring
            """
            return '-ovc {video_codec}'.format(video_codec=self.video_codec)

        def vcodec_opts():
            """
            Returns a video codec options argument substring
            """
            if not self.video_opts:
                return ''

            param = '{codec}opts'.format(codec=self.video_codec)

            if self.video_opts_prefix:
                param = self.video_opts_prefix

            return '-{param} {opts}'.format(
                param = param,
                opts  = self.video_opts
            )           

        def acodec():
            """
            Returns a audio codec (-oac) argument substring
            """
            if not self.audio_codec:
                return ''
            return '-oac {audio_codec}'.format(audio_codec=self.audio_codec)

        def acodec_opts():
            """
            Returns a audio codec options argument substring
            """
            if not self.audio_opts:
                return ''
            param = '{audio_codec}opts'.format(audio_codec=self.audio_codec)

            if self.audio_opts_prefix:
                param = self.audio_opts_prefix
            return '-{param} {opts}'.format(
                param = param,
                opts  = self.audio_opts
            )
        
        def sample_rate():
            """
            Returns a sample rate (-srate) argument substring
            """
            return '-srate %s' % self.sample_rate if self.sample_rate else ''

        def video_filters():
            """
            Returns a video filters (-vf) argument substring
            """
            bits = []

            if self.width and self.height:
                bits.append('scale={w}:{h}'.format(w=self.width,h=self.height))

            elif self.width and not self.height:
                bits.append('scale={w}:-'.format(w=self.width))

            elif not self.width and self.height:
                bits.append('scale=-:{h}'.format(h=self.height))

            return ('-vf '+','.join(bits)) if bits else ''

        cmd = ' '.join(['mencoder',
            input_filename(),    # Input filename
            output_filename(),   # Output filename (-o argument)
            container(),         # Format container (-of argument)
            vcodec(),            # Video codec (-ovc argument)
            vcodec_opts(),       # Video codec options
            acodec(),            # Audio codec (-oac argument)
            acodec_opts(),       # Audio codec options string
            sample_rate(),       # Sample rate
            video_filters(),     # Video filters (-vf argument) substring
        ])
        print cmd
        return cmd

    def parse_converter_output(self, input_file, output_file, **kwargs):
        """
        Track mencoder converting progress
        """
        command = self.get_encode_command(input_file, output_file)
        percent = {'percent':0}

        def line_handler(line, percent, process_handler):
            if 'Error parsing option on the command line' in line:
                raise WrongCommandLine, 'Parse error in command:\n%s\n' % command

            # Retrieve current progress position
            pos_match = re.compile('^Pos:.*?\(\s*?(\d+)%\)', re.U).match(line)
            
            if pos_match:
                curr = pos_match.group(1)
            
                if percent['percent'] != curr:
                    process_handler(int(percent['percent']), int(curr))
                    percent['percent'] = curr

        popen(command, line_handler, kwargs={
            'percent': percent,
            'process_handler': self.process_handler,
        })

        return True


class FFMpegConverter(BaseConverter):
    """
    FFMpeg converter base class
    """
    def parse_converter_output(self, input_file, output_file, **kwargs):
        """
        Track ffmpeg converting progress
        """
        command = self.get_encode_command(input_file, output_file)
        percent = {'percent': 0, 'duration': 0}

        def line_handler(line, re_duration, re_progress, percent):
            """
            Handles the ffmpeg stream lines
            """
            def time2sec(match):
                """
                Converts time pisition into seconds
                """
                g = match.group
                return 3600 * int(g(1)) + 60 * int(g(2)) + int(g(3)) 

            # Retrieve current progress position
            duration_match = re_duration.match(line)
            progress_match = re_progress.match(line)

            if duration_match: 
                duration = time2sec(duration_match) 
 
            if progress_match:
                curr = 0

                if duration:
                    curr = int(math.floor(time2sec(progress_match)*100/duration))

                if percent['percent'] != curr:
                    self.process_handler(int(percent['percent']), int(curr))
                    percent['percent'] = curr
        # End of loop
        popen('', line_handler, {
            're_duration' : re.compile('^Duration: (d{2}):(d{2}):(d{2}).(d{2})$', re.U),
            're_progress' : re.compile('time=(d{2}):(d{2}):(d{2})\.(\d{2})', re.U),
            'percent'     : percent,
        })  


class H263Converter(MencoderConverter):
    """
    The LAVC codec
    """
    video_codec = 'lavc'
    video_opts  = 'vcodec=flv:vbitrate=700:trell:v4mv:mv0:mbd=2:cbp:aic:cmp=3:subcmp=3'
    audio_codec = 'mp3lame'
    audio_opts  = 'abr:br=64'
    audio_opts_prefix = 'lameopts'

class H264Converter(MencoderConverter):
    """
    The X264 (Open h264 implementation) codec
    """    
    video_codec = 'x264'    
    video_opts = 'vcodec=x264:vbitrate=288:mbd=2:mv0:trell:v4mv:cbp:last_pred=3:predia=2:dia=2:vmax_b_frames=0:vb_strategy=1:precmp=2:cmp=2:subcmp=2:preme=2:qns=2'
    video_opts = ''
    video_opts_prefix = 'x264encopts'
    audio_codec = 'mp3lame'
    audio_opts  = 'abr:br=64'
    audio_opts_prefix = 'lameopts'


##############################################################################

if __name__ == '__main__':

    if len(sys.argv) < 3:
        print "Usage:\n%s <input_file> <output_file>" % sys.argv[0]
        sys.exit(1)

    converter = H264Converter(
        width  = 640,
        height = 480,
    )
    result = converter.convert(
        input_file = sys.argv[1], 
        output_file = sys.argv[2],
    )
