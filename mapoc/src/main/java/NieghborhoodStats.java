import org.neo4j.procedure.Context;
import org.neo4j.procedure.*;
import org.neo4j.graphdb.*;
import org.neo4j.logging.*;

import java.util.*;
import java.util.stream.Stream;

public class NieghborhoodStats {

    @Context
    public Log log;

    @Context
    public Transaction tx;


    public static class ClassPercentage {
        public double benign;
        public double malicious;
        public ClassPercentage(double benign, double malicious){
            this.benign = benign;
            this.malicious = malicious;
        }
    }

    private boolean isDomain(Node node){
        for(Label l: node.getLabels()) if(l.name().equals("Domain")) return true;
        return false;
    }

    private Pair<Long, Long> explore(HashSet<Node> seen, Node n){

        long b_cnt = 0;
        long total_cnt = 0;

        for(Relationship rel: n.getRelationships(Direction.OUTGOING)){
            Node neigh = rel.getEndNode();

            if(seen.contains(neigh)) continue;
            seen.add(neigh);
            if(!this.isDomain(neigh)) continue;
            long isBenign = (long) neigh.getProperty("label");
            b_cnt += isBenign;
            total_cnt++;
        }

        return new Pair<>(b_cnt,total_cnt);
    }

    private ClassPercentage getDirectNeighbors(Node start){

        HashSet<Node> seen = new HashSet<>();
        long total_cnt = 0;
        long b_cnt = 0;

        for(Relationship rel: start.getRelationships(Direction.OUTGOING)){
            Node neigh = rel.getEndNode();

            if(seen.contains(neigh)) continue;
            seen.add(neigh);

            if(!this.isDomain(neigh)) {
                Pair<Long, Long> vals = this.explore(seen, neigh);
                b_cnt += vals.first;
                total_cnt += vals.second;
                continue;
            }
            long isBenign = (long) neigh.getProperty("label");
            b_cnt += isBenign;
            total_cnt++;
        }
        if(total_cnt == 0) return new ClassPercentage(0.0, 0.0);

        double benign_percentage = (double) b_cnt / (double) total_cnt;
        return new ClassPercentage(benign_percentage, 1.0 - benign_percentage);
    }

    @Procedure(name="mapoc.stats.nieghPerc", mode = Mode.READ)
    @Description("Calculates percentage of benign and malicious domains that are one \"meta-path\" hop away")
    public Stream<ClassPercentage> calculateNeighborsPercentage(
            @Name("match") Map<String, Object> match
    ){
        Node start = HelperFuncs.getNodeFromMatch(match, this.tx);
        ClassPercentage result = this.getDirectNeighbors(start);
        return Stream.of(result);
    }

}
