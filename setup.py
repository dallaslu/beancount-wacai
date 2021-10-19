from setuptools import setup
from setuptools import find_packages

VERSION = '0.1.0'

with open('README.md', 'r', encoding='UTF-8') as f:
    LONG_DESCRIPTION = f.read()

with open('requirements.txt', 'r') as f:
    requirements = list(filter(None, f.read().split('\n')))

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
    install_requires=requirements,
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Topic :: Office/Business :: Financial :: Accounting',
    ],
    python_requires='>=3.6',
)
