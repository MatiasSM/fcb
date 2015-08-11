from setuptools import setup, find_packages

setup(
    name='Files_Cloud_Backuper',

    version='0.3.1',

    packages=find_packages(),

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
    keywords='backup storage internet',

    install_requires=['sqlalchemy', 'subprocess32', 'python-dateutil', 'numpy', 'pycrypto', 'pillow', 'circuits'],

    package_data={
        'sample_settings': ['fcb/config_example*.xml'],
    },

    entry_points={
        'console_scripts': [
            'fcb-upload = fcb.fcb_launcher:main',
            'fcb-direct-upload = fcb.files_cloud_backuper:main',
            'fcb-check = fcb.upload_checker:main',
            'fcb-untransform = fcb.untransform_file:main',
            'fcb-cleanup = fcb.db_cleanup:main',
            'fcb-createdb = fcb.database.schema:main',
        ]
    }
)
