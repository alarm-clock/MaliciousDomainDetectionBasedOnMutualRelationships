from enum import Enum


class NodeTypes(Enum):
    DOMAIN = 'Domain'
    DUMMY_DOMAIN = 'Du_domain'
    IP = 'IP'


class EdgeTypes(Enum):
    TRANSLATES = 'translates'
    SUBDOMAIN = 'subdomain'
    SUBDOMAIN_OF = 'subdomain_of'
    CNAME = 'cname'