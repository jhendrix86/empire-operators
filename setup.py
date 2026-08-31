from setuptools import setup, find_packages

setup(
    name="empire-operators",
    version="0.1.0",
    description="Fleet-installable extract of empire_os general reasoning operators + ASGI middleware",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.9",
    install_requires=[],  # pure Python, no runtime deps
    extras_require={"dev": ["pytest>=7.4.0"]},
    include_package_data=True,
    zip_safe=False,
)
