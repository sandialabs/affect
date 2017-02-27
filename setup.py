#!/usr/bin/env python

from setuptools import setup
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext
import pkg_resources
import distutils.ccompiler
import getpass
import glob
import os
from sys import platform as _platform
import multiprocessing.pool


class BuildExtensions(build_ext):
    """
    Subclass setuptools build_ext command. Does the following
    1) it makes sure numpy is available
    2) it injects numpy's core/include directory in the include_dirs parameter of all extensions
    3) it runs the original build_ext command
    """

    def run(self):
        # According to
        # https://pip.pypa.io/en/stable/reference/pip_install.html#installation-order
        # at this point we can be sure pip has already installed numpy
        numpy_includes = pkg_resources.resource_filename('numpy', 'core/include')
        for ext in self.extensions:
            if hasattr(ext, 'include_dirs') and numpy_includes not in ext.include_dirs:
                ext.include_dirs.append(numpy_includes)
        build_ext.run(self)

NUMBER_PARALLEL_COMPILES = 4

long_description = """
Affect is a library for processing computer simulation data on unstructured grids.
"""

# platform specific header and library directories
other_include = ''
other_library = ''

if _platform == 'linux' or _platform == 'linux2':
    os.environ["CC"] = 'gcc'
    os.environ["CXX"] = 'gcc'
    python_base = ''  # TODO: fix linux platform setup
    other_include = python_base + '/include'
    other_library = python_base + '/lib'
elif _platform == 'darwin':
    # prerequisite: brew install llvm (until Apple "clang -fopenmp" will work
    # export PATH="/usr/local/opt/llvm/bin:${PATH}"
    os.environ["CC"] = 'clang'
    os.environ["CXX"] = 'clang'
    user = getpass.getuser()
    python_base = '/Users/' + user + '/anaconda'
    other_include = python_base + '/include'
    other_library = python_base + '/lib'
elif _platform == 'win32':
    os.environ["CC"] = 'gcc'
    os.environ["CXX"] = 'gcc'
    python_base = ''  # TODO: fix win32 platform setup
    other_include = python_base + '/include'
    other_library = python_base + '/lib'

connect_source_files = ['affect/connect.pyx']
connect_source_files += glob.glob('c-mesh/*.cpp')
connect_include = 'c-mesh'

# Prerequisites:
#
# A prebuilt exodus exoIIv2c library
#
# Xcode command line tools
# Run "xcode-select --install"
#
# OpenMP threading
# "brew install llvm"
# may have to "export DYLD_LIBRARY_PATH=/usr/local/lib"
#
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

extensions = [
    Extension('affect.exodus',
              sources=['affect/exodus.pyx'],
              include_dirs=[other_include],
              libraries=['iomp5', 'exoIIv2c'],
              library_dirs=[other_library],
              extra_compile_args=[  # '-I/usr/local/opt/llvm/include',
                                  '-I/Users/kdcopps/Developer/exodus/exodus/cbind/include/',
                                  '-stdlib=libc++',
                                  '-mmacosx-version-min=10.11',
                                  '-fopenmp',
                                  '-Wno-unused-function', '-Wno-sometimes-uninitialized', '-Wno-unreachable-code'],
              extra_link_args=['-L/usr/local/opt/llvm/lib',
                               '-L/Users/kdcopps/Developer/exodus/exodus/cbind/',
                               '-mmacosx-version-min=10.11'],
              language="c++",
              ),
    Extension('affect.connect',
              include_dirs=[connect_include, other_include],
              sources=connect_source_files,
              libraries=['iomp5'],
              library_dirs=[other_library],
              extra_compile_args=[  # '-I/usr/local/opt/llvm/include',
                                  '-stdlib=libc++',
                                  '-mmacosx-version-min=10.11',
                                  '-fopenmp',
                                  '-Wno-unused-function', '-Wno-unneeded-internal-declaration', '-Wno-unused-variable'],
              extra_link_args=['-L/usr/local/opt/llvm/lib',
                               '-mmacosx-version-min=10.11'],
              language="c++",
              ),
]


def parallel_c_compile(self, sources, output_dir=None, macros=None, include_dirs=None, debug=0, extra_preargs=None,
                       extra_postargs=None, depends=None):
    """
    Function for monkey-patch of distutils.ccompiler to allow implement compilation of multip C/C++ files.
    """
    # those lines are copied from distutils.ccompiler.CCompiler directly
    macros, objects, extra_postargs, pp_opts, build = self._setup_compile(output_dir, macros, include_dirs, sources,
                                                                          depends, extra_postargs)
    cc_args = self._get_cc_args(pp_opts, debug, extra_preargs)

    def _single_compile(obj):
        try:
            src, ext = build[obj]
        except KeyError:
            return
        self._compile(obj, src, ext, cc_args, extra_postargs, pp_opts)

    # convert to list, imap is evaluated on-demand
    list(multiprocessing.pool.ThreadPool(NUMBER_PARALLEL_COMPILES).imap(_single_compile, objects))
    return objects

# Monkey patch to allow parallel compile
distutils.ccompiler.CCompiler.compile = parallel_c_compile

setup(
    name='affect',
    description='Affect - Processing Computational Simulations',
    long_description=long_description,
    license='MIT',
    version='0.1',
    author='Kevin Copps',
    author_email='kdcopps@sandia.gov',
    maintainer='Kevin Copps',
    maintainer_email='kdcopps@sandia.gov',
    url='https://github.com/kdcopps/affect',
    packages=['affect'],
    classifiers=['Programming Language :: Python :: 3', ],
    setup_requires=['setuptools>=18.0', 'numpy', 'cython', 'pytest-runner'],
    install_requires=requirements,
    tests_require=['pytest'],
    zip_safe=False,
    cmdclass={'build_ext': BuildExtensions},
    ext_modules=extensions
)
