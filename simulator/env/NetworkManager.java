package env;

import java.util.*;

public class NetworkManager {
    public static class Edge {
        public final String from;
        public final String to;
        public final double weight;

        private static final double DEFAULT_WEIGHT = 0;

        private Edge(String from, String to) {
            this(from, to, DEFAULT_WEIGHT);
        }

        private Edge(String from, String to, double weight) {
            this.from = from;
            this.to = to;
            this.weight = weight;
        }

        @Override
        public boolean equals(Object obj) { 
            if (this == obj) return true;
            if (obj == null || getClass() != obj.getClass()) return false;
            Edge edge = (Edge) obj;
            return from.equals(edge.from) && to.equals(edge.to);
        }

        @Override
        public int hashCode() {
            return Objects.hash(from, to);
        }
    }

    private static final double DEFAULT_WEIGHT = 1;

    private final Set<Edge> socialNetwork = Collections.synchronizedSet(new HashSet<>());

    //If already exists, it will be ignored.
    public void addEdge(String from, String to, double weight) {
        Edge link = new Edge(from, to, weight);
        socialNetwork.add(link);
    }

    public void addEdge(String from, String to) {
        addEdge(from, to, DEFAULT_WEIGHT);
    }

    public void removeEdge(String from, String to) {
        Edge link = new Edge(from, to);
        socialNetwork.remove(link);
    }

    public Set<Edge> getSocialNetwork() {
        return Collections.unmodifiableSet(socialNetwork);
    }
}
