package env;

import jason.asSyntax.*;
import jason.asSemantics.Agent;
import jason.asSemantics.Unifier;
import java.util.*;

public class ExampleKnowledgeManager implements KnowledgeManager {

    private final Agent agent = new Agent();

    public ExampleKnowledgeManager() {
        agent.initAg();
        load();
    }

    private void load() {
        try {
            // Hechos
            addFact("norma(comunicacion_respetuosa)");
            addFact("norma(verificar_informacion)");
            addFact("norma(no_discurso_odio)");
            addFact("causa(cambio_climatico, gases_efecto_invernadero)");
            addFact("efecto(cambio_climatico, aumento_temperaturas)");
            addFact("efecto(cambio_climatico, aumento_nivel_mar)");
            addFact("solucion(cambio_climatico, reducir_emisiones)");
            addFact("solucion(cambio_climatico, reforestar)");

            addRule("problema_grave(X) :- causa(X, _) & efecto(X, _).");
            addRule("tiene_solucion(X) :- solucion(X, _).");
            addRule("eliminar_publicacion(U,P) :- viola(P,Norma) & norma(Norma).");
            addRule("activista(U,cambio_climatico) :- publicacion(U,solucion(cambio_climatico,X)) & solucion(cambio_climatico,X).");
        } catch (Exception e) {
            throw new RuntimeException("Failed to load knowledge base: " + e.getMessage(), e);
        }
    }

    private void addFact(String s) throws Exception {
        agent.getBB().add(ASSyntax.parseLiteral(s));
    }

    private void addRule(String s) throws Exception {
        agent.getBB().add(ASSyntax.parseRule(s));
    }

    @Override
    public List<Literal> query(Literal queryLiteral) {
        List<Literal> results = new ArrayList<>();
        Iterator<Unifier> it = queryLiteral.logicalConsequence(agent, new Unifier());
        while (it.hasNext()) {
            Unifier u = it.next();
            results.add((Literal) queryLiteral.capply(u));
        }
        return results;
    }
}