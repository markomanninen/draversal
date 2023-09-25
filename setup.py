# run tests: python -m unittest discover -s tests -p 'test*.py'
# create dist: python setup.py sdist bdist_wheel
# publish to pypi: python -m twine upload dist/*

from setuptools import setup, find_packages

setup(
    name='draversal',
    version='0.1.1',
    packages=find_packages(),
    author='Marko T. Manninen',
    author_email='elonmedia@gmail.com',
    description='A package for depth-first traversal of Python dictionaries with uniform child fields, supporting both forward and backward navigation.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/markomanninen/draversal',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)
