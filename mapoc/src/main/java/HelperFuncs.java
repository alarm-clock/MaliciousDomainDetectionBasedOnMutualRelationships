import org.neo4j.graphdb.Label;
import org.neo4j.graphdb.Node;
import org.neo4j.graphdb.NotFoundException;
import org.neo4j.graphdb.Transaction;

import java.util.Map;
import java.util.List;

public class HelperFuncs {

    public static Node getNodeFromMatch(Map<String, Object> match, Transaction tx){
        String labelStr = (String) match.get("label");
        if(labelStr == null) {
            throw new IllegalArgumentException("match must contain at least label");
        }
        match.remove("label");

        List<Node> found = tx.findNodes(Label.label(labelStr), match).stream().toList();
        if (found.size() > 1){
            throw new NotFoundException("Multiple nodes have been found with given label and attributes");
        }
        if( found.isEmpty()){
            throw new NotFoundException("There is no node that would match given values");
        }
        return found.get(0);
    }
}

