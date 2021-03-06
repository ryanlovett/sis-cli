import setuptools

setuptools.setup(
	name='sis',
	version='0.2',
	description='Query the UC Berkeley SIS.',
	url='https://github.com/ryanlovett/sis',
	author='Ryan Lovett',
	author_email='rylo@berkeley.edu',
	packages=setuptools.find_packages(),
	install_requires=[
	  'aiohttp', 'jmespath'
	],
    entry_points={
        'console_scripts': [
            'sis= sis.__main__:run',
        ],
    },

)
