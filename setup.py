# run tests: python -m unittest discover -s tests -p 'test*.py'
# create dist: python setup.py sdist bdist_wheel
# publish to pypi: python -m twine upload dist/*

from setuptools import setup, find_packages

setup(
    name='draversal',
    version='0.2.0',
    packages=find_packages(),
    package_data={'draversal_ui': ['index.html']},
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
    extras_require={
        # mcp 2.x renamed FastMCP to MCPServer; server.py uses the 1.x API
        'mcp': ['mcp>=1.2,<2', 'jsonschema'],
    },
    entry_points={
        'console_scripts': [
            'draversal-mcp=draversal_mcp.server:main',
            'draversal-store=draversal_mcp.cli:main',
            'draversal-ui=draversal_ui.server:main',
        ],
    },
)
