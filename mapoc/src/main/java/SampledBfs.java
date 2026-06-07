
import org.neo4j.procedure.Context;
import org.neo4j.procedure.*;
import org.neo4j.graphdb.*;
import org.neo4j.logging.*;

import java.util.*;
import java.util.stream.Stream;
import java.util.stream.StreamSupport;

public class SampledBfs {
    @Context
    public GraphDatabaseService db;

    @Context
    public Log log;

    @Context
    public Transaction tx;

    public static class RelId {
        public String relId;
        public RelId(String relId){this.relId = relId;}
    }

    private class BFSIterator implements Iterator<RelId> {
        private ArrayList<Node> frontier = new ArrayList<>();
        private ArrayList<Node> next = new ArrayList<>();
        private final HashSet<String> visited = new HashSet<>();
        private final Queue<RelId> buff = new ArrayDeque<>();
        private final Random rand;

        private final long maxDepth;
        private final long maxNeighToSample;
        private final boolean backEdges;

        private int currDepth = 0;
        private boolean algoDone = false;

        BFSIterator(Node start, long maxDepth, long maxNeighToSample, boolean backEdges, long seed){
            this.maxDepth = maxDepth;
            this.maxNeighToSample = maxNeighToSample;
            this.backEdges = backEdges;
            this.rand = new Random(seed);

            frontier.add(start);
            visited.add(getNodeId(start));
        }

        String getNodeId(Node node){
            return node.getLabels().iterator().next().name() + node.getProperty("node_id");
        }

        private void bfsLoop(){
            while(this.buff.isEmpty() && this.currDepth < this.maxDepth)
            {
                if(this.frontier.isEmpty()) return;

                Node u = this.frontier.getFirst();
                this.frontier.removeFirst();
                int nNeighbours = u.getDegree(Direction.OUTGOING);
                boolean tooMany = nNeighbours > this.maxNeighToSample;
                double sample = (double) this.maxNeighToSample / (double) nNeighbours;

                for(Relationship rel: u.getRelationships(Direction.OUTGOING))
                {
                    Node v = rel.getEndNode();
                    String v_label = v.getLabels().iterator().next().name();
                    if(Objects.equals(v_label, "Tmp_domain")) continue;
                    if( visited.contains(v_label + v.getProperty("node_id")))
                    {
                        if(backEdges) this.buff.add(new RelId(rel.getElementId()));//addLast(new RelId(rel.getElementId()));
                        continue;
                    }
                    if(tooMany)
                    {
                        if(rand.nextDouble() > sample) continue;
                    }
                    this.next.addLast(v);
                    this.buff.add(new RelId(rel.getElementId())); //addLast
                }
                this.visited.add(getNodeId(u));

                if(this.frontier.isEmpty())
                {
                    this.frontier = this.next;
                    this.next = new ArrayList<>();
                    this.currDepth++;
                    if(this.frontier.isEmpty()) return;
                }
            }
            if(this.currDepth >= this.maxDepth) this.algoDone = true;
        }

        private void lastBackEdges(){
            while( this.buff.isEmpty() && !this.frontier.isEmpty())
            {
                Node u = this.frontier.getFirst();
                this.frontier.removeFirst();

                for (Relationship rel : u.getRelationships(Direction.OUTGOING)) {
                    Node v = rel.getEndNode();
                    if (visited.contains(this.getNodeId(v))) {
                        this.buff.add(new RelId(rel.getElementId()));
                    }
                }
            }
        }

        @Override
        public boolean hasNext(){
            this.calcNext();
            return !this.buff.isEmpty();
        }

        @Override
        public RelId next(){
            this.calcNext();
            if(this.buff.isEmpty()) throw new NoSuchElementException();
            return this.buff.poll();
        }

        private void calcNext(){
            if(!this.algoDone) this.bfsLoop();
            else {
                if(this.backEdges) this.lastBackEdges();
            }
        }
    }

    private void _bfs(Node start, long maxDepth, long maxNeighboursToSample, boolean backEdges, long seed, ArrayList<RelId> result){

        ArrayList<Node> frontier = new ArrayList<>();
        ArrayList<Node> next = new ArrayList<>();
        HashSet<String> visited = new HashSet<>();
        Random rand = new Random(seed);

        frontier.addLast(start);
        visited.add(start.getLabels().iterator().next().name() + start.getProperty("node_id"));

        for(int currDepth = 0; currDepth < maxDepth - 1; currDepth++) //-1 is because otherwise nodes from maxDepth + 1 are also returned
        {
            for (Node u: frontier) {

                int nNeighbours = u.getDegree(Direction.OUTGOING);
                boolean tooMany = nNeighbours > maxNeighboursToSample;
                double sample = (double) maxNeighboursToSample / (double) nNeighbours;

                for(Relationship rel: u.getRelationships(Direction.OUTGOING))
                {
                    Node v = rel.getEndNode();
                    String v_label = v.getLabels().iterator().next().name();
                    if(Objects.equals(v_label, "Tmp_domain")) continue;
                    if( visited.contains(v_label + v.getProperty("node_id")))
                    {
                        if(backEdges) result.addLast(new RelId(rel.getElementId()));
                        continue;
                    }
                    if(tooMany)
                    {
                        if(rand.nextDouble() > sample) continue;
                    }
                    next.addLast(v);
                    result.addLast(new RelId(rel.getElementId()));
                }

                visited.add(u.getLabels().iterator().next().name() + u.getProperty("node_id"));
            }
            frontier = next;
            if( frontier.isEmpty()) break;
            next = new ArrayList<>();
        }
        if(backEdges) {
            for (Node u : frontier) {
                for (Relationship rel : u.getRelationships(Direction.OUTGOING)) {
                    Node v = rel.getEndNode();
                    if (visited.contains(v.getLabels().iterator().next().name() + v.getProperty("node_id"))) {
                        result.addLast(new RelId(rel.getElementId()));
                    }
                }
            }
        }
    }

    @Procedure(name="mapoc.sampling.bfsStream", mode = Mode.READ)
    @Description("Performs custom bfs with sampling to get k-hop neighborhood while streaming results")
    public Stream<RelId> bfsStream(
            @Name("match") Map<String, Object> match,
            @Name("maxDepth") long maxDepth,
            @Name("maxNeighToSample") long maxNeighToSample,
            @Name("backEdges") boolean backEdges,
            @Name("seed") long seed
    ){
        //ArrayList<RelId> result = new ArrayList<>();
        if (maxDepth < 1){
            throw new IllegalArgumentException("Depth must be at least 1");
        }
        String labelStr = (String) match.get("label");
        if (labelStr == null){
            throw new IllegalArgumentException("match must contain at least label");
        }
        match.remove("label");

        List<Node> found = tx.findNodes(Label.label(labelStr), match).stream().toList();
        if(found.size() > 1)
        {
            throw new NotFoundException("Multiple nodes have been found with given label and attributes");
        }
        if(found.isEmpty()) return Stream.empty();

        Node start = found.get(0);

        Iterator<RelId> relIdIterator = new BFSIterator(start,maxDepth,maxNeighToSample,backEdges,seed);

        return StreamSupport.stream( Spliterators.spliteratorUnknownSize(relIdIterator,0), false);
    }

    @Procedure(name="mapoc.sampling.bfsStreamNdId", mode = Mode.READ)
    @Description("Performs custom bfs with sampling to get k-hop neighborhood while streaming results")
    public Stream<RelId> bfsStreamNdId(
            @Name("label") String label,
            @Name("startNodeId") long startNodeId,
            @Name("maxDepth") long maxDepth,
            @Name("maxNeighToSample") long maxNeighToSample,
            @Name("backEdges") boolean backEdges,
            @Name("seed") long seed
    ){

        Node start = tx.findNode(Label.label(label),"node_id",startNodeId);
        if( start == null) return Stream.empty();

        Iterator<RelId> relIdIterator = new BFSIterator(start,maxDepth,maxNeighToSample,backEdges,seed);
        return StreamSupport.stream( Spliterators.spliteratorUnknownSize(relIdIterator,0), false);
    }

    @Procedure(name="mapoc.sampling.bfs", mode = Mode.READ)
    @Description("Performs custom bfs with sampling")
    public Stream<RelId> bfs(
            @Name("match") Map<String, Object> match,
            @Name("maxDepth") long maxDepth,
            @Name("maxNeighboursToSample") long maxNeighboursToSample,
            @Name("BackEdges") boolean backEdges,
            @Name("seed") long seed
    ){
        ArrayList<RelId> result = new ArrayList<>();
        if (maxDepth < 1){
            throw new IllegalArgumentException("Depth must be at least 1");
        }
        String labelStr = (String) match.get("label");
        if (labelStr == null){
            throw new IllegalArgumentException("match must contain at least label");
        }
        match.remove("label");

        try (Transaction tx = db.beginTx()){

            List<Node> found = tx.findNodes(Label.label(labelStr), match).stream().toList();
            if(found.size() > 1)
            {
                throw new NotFoundException("Multiple nodes have been found with given label and attributes");
            }
            if(found.isEmpty())
            {
                tx.commit();
                return result.stream();
            }

            Node start = found.get(0);
            _bfs(start,maxDepth,maxNeighboursToSample,backEdges,seed,result);
            tx.commit();
        }
        return result.stream();
    }

    @Procedure(name="mapoc.sampling.bfs_nd_id", mode = Mode.READ)
    @Description("Performs custom bfs with sampling, start node is found using node_id")
    public Stream<RelId> bfs_nd_id(
            @Name("startLabel") String label,
            @Name("startNodeId") long startNodeId,
            @Name("maxDepth") long maxDepth,
            @Name("maxNeighboursToSample") long maxNeighboursToSample,
            @Name("BackEdges") boolean backEdges,
            @Name("seed") long seed
    ){


        ArrayList<RelId> result = new ArrayList<>();
        if (maxDepth < 1){
            throw new IllegalArgumentException("Depth must be at least 1");
        }

        try (Transaction tx = db.beginTx()){

            Node start = tx.findNode(Label.label(label), "node_id", startNodeId);
            if (start == null)
            {
                tx.commit();
                return result.stream();
            }
            _bfs(start,maxDepth,maxNeighboursToSample,backEdges,seed,result);
            tx.commit();
        }
        return result.stream();
    }
}
