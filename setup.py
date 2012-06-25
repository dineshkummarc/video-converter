#!/usr/bin/env python
from distutils.core import setup
import os

version='0.4.5'
package = 'video_converter'

setup(
    name = 'video-converter',
    version = version,
    author  = 'marazmiki',
    author_email = 'marazmiki@gmail.com',
    url = 'http://bitbucket.org/marazmiki/video-converter/',
    download_url = 'http://bitbucket.org/marazmiki/video-converter/',
    description = 'Video tools for web video converting',
    long_description = '', #open('README.rst').read(),
    license = 'MIT license',
    py_modules = ['conv'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)

