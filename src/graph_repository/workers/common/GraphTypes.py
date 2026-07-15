"""
File: GraphTypes.py
Author: Jozef Michal Bukas <xbukas00@stud.fit.vutbr.cz>
"""
from enum import Enum


class NodeTypes(Enum):

    DOMAIN = ('Domain','d', 0)
    DUMMY_DOMAIN = ('Du_domain', 'du', 1)
    TMP_DOMAIN = ('Tmp_domain', 'tm', 2),
    REGISTRANT = ('Registrant', 'r', 3),
    CERTIFICATE = ('Certificate', 'c', 4),
    IP = ('IP','ip',5) #since python guarantees that attributes are in the same order as they are written I can do dirty trick
              #but one that makes my life easier, that when I want filter out supporting nodes then I just go until
              # I hit IP
              #IP MUST BE LAST DATA NODE, SOME PARTS OF CODE DEPENDENT ON THIS

    #supporting node types
    DUMMY_SUB_DOMAIN = ('Sdu_sub_domain','none',4)  #all dummy domains that will be created after initial creation must have prefix Sdu_
    CURRENT_VERSION = ('CurrentGraphVersion','none',4)
    VERSION = ('GraphVersion','none',4)
    ND_ID_CNT = ('NodeIdCnt','none',4)
    MAINTENANCE = ('Maintenance','none',4)


    def __init__(self, neo4j: str, dgl: str, dgl_code: int):
        self._neo4j = neo4j
        self._dgl = dgl
        self._dgl_code = dgl_code

    @property
    def neo4j(self) -> str:
        return self._neo4j

    @property
    def dgl(self) -> str:
        return self._dgl

    @property
    def dgl_code(self) -> int:
        return self._dgl_code

    @staticmethod
    def from_str(n_t: str):

        for node in NodeTypes:
            if n_t == node.neo4j:
                return node
            if n_t == node.dgl:
                return node

        return None

    @staticmethod
    def get_data_n_t() -> list:
        data = []
        for node in NodeTypes:
            data.append(node)
            if node == NodeTypes.IP:
                break

        return data
    
    @staticmethod
    def get_data_n_t_str() -> list[str]:
        data = []
        for node in NodeTypes:
            data.append(node.neo4j)
            if node == NodeTypes.IP:
                break

        return data

    @staticmethod
    def get_supporting_dummies_n_t() -> list:
        dummies = []
        prefix = "Sdu_"
        for node in NodeTypes:
            type_prefix = node.neo4j[:len(prefix)]
            if type_prefix == prefix:
                dummies.append(node)

        return dummies

    @staticmethod
    def from_neo4j_to_dgl(n_t: str, du_domain_as_domain: bool = False) -> str | None:
        for node in NodeTypes:
            if n_t == node.neo4j:
                if du_domain_as_domain and node == NodeTypes.DUMMY_DOMAIN:
                    return NodeTypes.DOMAIN.dgl
                return node.dgl

        return None

    @staticmethod
    def from_neo4j_to_dgl_code(n_t: str) -> int | None:
        for node in NodeTypes:
            if n_t == node.neo4j:
                return node.dgl_code

        return None

    @staticmethod
    def from_dgl_to_dgl_code(n_t: str) -> int | None:
        for node in NodeTypes:
            if n_t == node.dgl:
                return node.dgl_code

        return None


NODE_ID = 'node_id'
IP_STR = 'ip_str'
IP_VERSION = 'ip_version'
REG_NAME = 'name'
CERT_CN = 'cn'
CERT_ORG = 'org'
CERT_SUBJ_K_ID = 'subj_key_id'
CERT_BEFORE = 'not_before'
CERT_AFTER = 'not_after'
CERT_HASH = 'data_hash'
D_NAME = 'domain_name'
D_LABEL = 'label'
D_DEPTH = 'depth'
D_PARENT_DOMAINS = 'parent_domains'

NODE_ATTRIBUTES: dict[NodeTypes, list[str]] = {
    NodeTypes.IP: [IP_STR, IP_VERSION, NODE_ID],
    NodeTypes.REGISTRANT: [REG_NAME, NODE_ID],
    NodeTypes.CERTIFICATE: [CERT_CN, CERT_ORG, CERT_SUBJ_K_ID, CERT_BEFORE, CERT_AFTER, CERT_HASH, NODE_ID],
    NodeTypes.DOMAIN: [D_NAME, D_LABEL, D_DEPTH, D_PARENT_DOMAINS, NODE_ID],
    NodeTypes.DUMMY_DOMAIN: [D_NAME, D_DEPTH, D_PARENT_DOMAINS, NODE_ID],
    NodeTypes.DUMMY_SUB_DOMAIN: [D_NAME, D_DEPTH, D_PARENT_DOMAINS, NODE_ID]
}


class EdgeTypes(Enum):
    TRANSLATES = 'translates'
    SUBDOMAIN = 'subdomain'
    SUBDOMAIN_OF = 'subdomain_of'
    CNAME = 'cname',
    REGISTERED = 'registered',
    HAS_CERTIFICATE = 'has_certificate',
    NULL = 'null'

    @staticmethod
    def from_str(e_t: str):

        for edge in EdgeTypes:
            if e_t == edge.value:
                return edge

        return None

    @staticmethod
    def e_t_builder_for_dgl(e_t: str, u_t: str, v_t: str) -> tuple[str,str,str]:
        e_t = e_t.split('_')[0]
        return u_t,f'{e_t}_{u_t}_{v_t}',v_t