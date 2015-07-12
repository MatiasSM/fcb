
from setuptools import setup, find_packages

setup(
    name='Files Cloud Backuper',
    version='0.3.0',
    packages=['utils', 'sending', 'sending.mail', 'sending.mega', 'sending.debug', 'sending.directory', 'database',
              'framework', 'framework.workflow', 'processing', 'processing.models', 'processing.filters',
              'processing.filesystem', 'processing.transformations'],
    url='https://github.com/MatiasSM/fcb',
    license='LGPL v3.0',
    author='MatiasSM',
    author_email='',
    description='Files Cloud Backuper (FCB) automates the process of uploading files to cloud storage services',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Archiving :: Backup',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Programming Language :: Python :: 2.7',
    ],
    # What does your project relate to?
    keywords='backup storage internet',
    packages=find_packages(),

    install_requires=['sqlalchemy', 'subprocess32', 'python-dateutil', 'python-numpy', 'pycrypto'],

    package_data={
        'sample_settings': ['fcb/config_example*.xml'],
    },

    entry_points={
        'console_scripts': [
            'fcb-upload = fcb.files_cloud_backuper:main',
            'fcb-check = fcb.upload_checker:main',
            'fcb-untransform = fcb.untransform_file:main',
            'fcb-cleanup = fcb.db_cleanup:main',
            ]
    }
)
