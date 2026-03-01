import importlib
import pkgutil
from misc.Logger import MyLogger


def get_options_from_registry(register: dict, options: list) -> None:
    """
    Get options from package register
    :param register: `dict` Register of classes from which options will be extracted
    :param options: `list` List into which options will be extracted
    :return: `None`
    """
    classes = ""
    for cls in register.values():
        options.extend(cls.available_options)
        classes += f"{cls.worker_name},"

    MyLogger.get_instance().log_debug(f"Loaded options from workers: {classes[:-1]} from module dataset_edge_workers")
    return


def import_all_modules_from_package(package_path: str, register: dict | None = None,
                                    options: list | None = None) -> bool:
    """
    Import all modules from a package, optionally also get their options from register
    :param package_path: `str` Path to the package in dot notation
    :param register: `dict` Register in which all modules store their options. If `None` then no options will be extracted
    :param options: `list` List into which options will be extracted. If `None` no options will be extracted.
    :return: True on success false otherwise
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
        get_options_from_registry(register, options)

    MyLogger.get_instance().log_debug(f"Imported all modules from {package_path}")
    return True
