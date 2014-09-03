# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from setuptools import setup, find_packages

setup(
    name='relengapi-slaveloan',
    version='0.1',
    description='Slave Loan blueprint for relengapi',
    author='Justin Wood',
    author_email='callek@mozilla.com',
    url='',
    install_requires=[
        "Flask",
        "relengapi",
    ],
    extras_require = {
        'test': [
            'nose',
            'mock'
        ]
    },
    packages=find_packages(),
    package_data={  # NOTE: these files must *also* be specified in MANIFEST.in
        'relengapi.blueprints.slaveloan': [
            'src/*/*.rst',
            'src/conf.py',
            'templates/*.html',
        ],
    },
    include_package_data=True,
    namespace_packages=['relengapi', 'relengapi.blueprints'],
    entry_points={
        "relengapi_blueprints": [
            'slaveloan = relengapi.blueprints.slaveloan:bp',
        ],
    },
    license='MPL2',
)
