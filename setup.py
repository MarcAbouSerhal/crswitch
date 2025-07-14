from setuptools import setup, find_packages

setup(
    name = 'crswitch',
    version = '1.0',
    packages = find_packages(),  # Automatically find package folders
    author = 'Marc Abou Serhal',
    author_email = 'marcabouserhal@gmail.com',
    description = 'No description available',
    long_description = open('README.md').read(),
    long_description_content_type = 'text/markdown',
    url = 'https://github.com/MarcAbouSerhal/crswitch',
    classifiers = [
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires = '>=3.1',
)
