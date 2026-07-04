"""
File: import_utils.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
Date: 29.12.2025
Brief: File that contains helper functions for importing all modules from package
    and extracting registered functions or options
"""

import importlib
import pkgutil
from typing import Iterable, Callable
from misc.Logger import MyLogger


def get_functions_from_registry(register: dict, funcs: list) -> None:
    """
    Function that extracts registered functions into output list
    :param register: `dict` registry of functions
    :param funcs: `list` list into which functions will be extracted
    :return: `None`
    """
    for func in register.values():
        funcs.append(func)

    return


def get_options_from_registry(register: dict, options: list) -> None:
    """
    Function that extracts options from registered classes into output list
    :param register: `dict` register of classes from which options will be extracted
    :param options: `list` list into which options will be extracted
    :return: `None`
    """
    classes = ""
    for cls in register.values():

        opts = cls.opts()
        if type(opts) == list or type(opts) == Iterable:
            options.extend(opts)
        else:
            options.append(opts)

        if hasattr(cls, "worker_name"):
            classes += f"{cls.worker_name},"

    if classes != "":
        MyLogger.get_instance().log_debug(f"Loaded options from workers: {classes[:-1]} from module")
    return


def import_all_modules_from_package(package_path: str, register: dict | None = None,
                                    options: list | None = None) -> bool:
    """
    Function that imports all modules from given package and optionally extracts registry values
    :param package_path: `str` path to the package in dot notation
    :param register: `dict | None` register in which imported modules store their options or functions
    :param options: `list | None` list into which extracted options or functions will be stored
    :return: `bool` True on success, otherwise False
    """

    MyLogger.get_instance().log_debug(f"Importing all modules from {package_path}")
    package = importlib.import_module(package_path)

    if not hasattr(package, '__path__'):
        MyLogger.get_instance().log_error(f"Path {package_path} is not a package, can not import")
        return False

    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        module_path = f"{package_path}.{module_name}"
        importlib.import_module(module_path)

    if register is not None and options is not None:

        if len(register) > 0:
            if type(list(register.values())[0]) != Callable:
                get_options_from_registry(register, options)
            else:
                get_functions_from_registry(register, options)

    MyLogger.get_instance().log_debug(f"Imported all modules from {package_path}")
    return True