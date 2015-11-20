from setuptools import setup


setup(
    name='rebind',
    version='0.1',
    author='Alexander Schepanovski',
    author_email='suor.web@gmail.com',

    description='Rebind hard-coded constants on the fly',
    long_description=open('README.rst').read(),
    url='http://github.com/Suor/rebind',
    license='BSD',

    py_modules=['rebind'],
    install_requires=[
        'byteplay>=0.2',
        'funcy>=1.6',
    ],

    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',

        'Intended Audience :: Developers',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
