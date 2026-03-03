from enum import Enum



class NodeTypes(Enum):

    DOMAIN = 'Domain'
    DUMMY_DOMAIN = 'Du_domain'
    TMP_DOMAIN = 'Tmp_domain'
    IP = 'IP' #since python guarantees that attributes are in the same order as they are written I can do dirty trick
              #but one that makes my life easier that when I want filter out supporting nodes then I just go until
              # I hit IP
              #IP MUST BE LAST DATA NODE, SOME PARTS OF CODE ARE DEPENDENT ON THIS

    #supporting node types
    DUMMY_SUB_DOMAIN = 'Du_sub_domain'
    CURRENT_VERSION = 'CurrentGraphVersion'
    VERSION = 'GraphVersion'
    ND_ID_CNT = 'NodeIdCnt'

    @staticmethod
    def from_str(n_t: str):

        for node in NodeTypes:
            if n_t == node.value:
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
            data.append(node.value)
            if node == NodeTypes.IP:
                break

        return data

class EdgeTypes(Enum):
    TRANSLATES = 'translates'
    SUBDOMAIN = 'subdomain'
    SUBDOMAIN_OF = 'subdomain_of'
    CNAME = 'cname'

    @staticmethod
    def from_str(e_t: str):

        for edge in EdgeTypes:
            if e_t == edge.value:
                return edge

        return None