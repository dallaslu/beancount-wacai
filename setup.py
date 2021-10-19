from setuptools import setup
from setuptools import find_packages

VERSION = '0.1.1'

with open('README.md', 'r', encoding='UTF-8') as f:
    LONG_DESCRIPTION = f.read()

setup(
    name='beancount-wacai',
    version=VERSION,
    url='https://github.com/dallaslu/beancount-wacai',
    project_urls={
        "Issue tracker": "https://github.com/dallaslu/beancount-wacai/issues",
    },
    author='Dallas Lu',
    author_email='914202+dallaslu@users.noreply.github.com',
    description='Import Wacai xlsx to Beancount',
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    install_requires=[
        'beancount>=2.3.4',
        'pypinyin>=0.43.0',
        'xlwings>=0.24.9',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Topic :: Office/Business :: Financial :: Accounting',
    ],
    python_requires='>=3.6',
)
