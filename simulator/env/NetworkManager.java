package env;

import java.util.*;

public class NetworkManager {
    private static class Edge {
        private static final double DEFAULT_WEIGHT = 1.0;

        private final String from;
        private final String to;
        private double weight;

        private Edge(String from, String to) {
            this(from, to, DEFAULT_WEIGHT);
        }

        private Edge(String from, String to, double weight) {
            this.from = from;
            this.to = to;
            this.weight = weight;
        }

        private void updateWeight(double weight) {
            this.weight = weight;
        }

        @Override
        public boolean equals(Object obj) { 
            if (this == obj) return true;
            if (obj == null || getClass() != obj.getClass()) return false;
            Edge edge = (Edge) obj;
            return from.equals(edge.from) && to.equals(edge.to);
        }
    }

    private final Set<Edge> socialNetwork = Collections.synchronizedSet(new HashSet<>());

    public void addEdge(String from, String to) {
        Edge link = new Edge(from, to);
        socialNetwork.add(link);
    }

    public void removeEdge(String from, String to) {
        Edge link = new Edge(from, to);
        socialNetwork.remove(link);
    }
}
