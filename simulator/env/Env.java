package env;

import jason.asSyntax.*;
import static jason.asSyntax.ASSyntax.*;
import jason.environment.Environment;

import java.util.*;

import lib.JasonToJavaTranslator;
import lib.JavaToJasonTranslator;
import initializer.MessageLoader;
import initializer.NetworkLoader;
import initializer.PublicProfileLoader;

public class Env extends Environment {

    private final NetworkManager networkManager = new NetworkManager();
    // private final ContentManager contentManager = new DefaultContentManager(networkManager);
    private final ContentManager contentManager = new CoNVaIContentManager(networkManager);
    private final KnowledgeManager knowledgeManager = new DefaultKnowledgeManager();
    private final Map<String, Map<String, String>> publicProfiles = new HashMap<>();

    @Override
    public void init(String[] args) {
        try {
            MessageLoader.load(contentManager, "initializer/messages.csv");
            PublicProfileLoader.load(publicProfiles, "initializer/public_profiles.csv");
            NetworkLoader.load(networkManager, this, "initializer/network.csv");
        } catch (Exception e) {
            throw new RuntimeException("Failed to initialize: " + e.getMessage(), e);
        }
    }

    @Override
    public boolean executeAction(String agent, Structure action) {
        boolean result = switch (action.getFunctor()) {
            case "updateFeed"      -> updateFeed(agent, action);
            case "searchContent"   -> searchContent(agent, action);
            case "searchAuthor"    -> searchAuthor(agent, action);
            case "createPost"      -> createPost(agent, action);
            case "repost"          -> repost(agent, action);
            case "comment"         -> comment(agent, action);
            case "react"           -> react(agent, action);
            case "ask"             -> ask(agent, action);
            case "createLink"      -> createLink(agent, action);
            case "removeLink"      -> removeLink(agent, action);
            case "readPublicProfile" -> readPublicProfile(agent, action);
            default -> { System.out.println("Unknown action: " + action); yield true; }
        };
        return result;
    }

    private boolean updateFeed(String agent, Structure action) {
        boolean includePublicVars = action.getArity() >= 1
            && JasonToJavaTranslator.translateBoolean(action.getTerm(0));
        List<MessageWithVars> feed = contentManager.feedFilter(agent, includePublicVars);
        updatePercepts(agent, feed, includePublicVars);
        return true;
    }

    private boolean searchContent(String agent, Structure action) {
        String concept = JasonToJavaTranslator.translateString(action.getTerm(0));
        boolean includePublicVars = action.getArity() >= 2
            && JasonToJavaTranslator.translateBoolean(action.getTerm(1));
        List<MessageWithVars> feed = contentManager.topicFilter(agent, concept, includePublicVars);
        updatePercepts(agent, feed, includePublicVars);
        return true;
    }

    private boolean searchAuthor(String agent, Structure action) {
        String author = JasonToJavaTranslator.translateString(action.getTerm(0));
        boolean includePublicVars = action.getArity() >= 2
            && JasonToJavaTranslator.translateBoolean(action.getTerm(1));
        List<MessageWithVars> feed = contentManager.authorFilter(agent, author, includePublicVars);
        updatePercepts(agent, feed, includePublicVars);
        return true;
    }

    private void updatePercepts(String agent, List<MessageWithVars> messages, boolean includePublicVars) {
        clearPercepts(agent);

        messages.forEach(mwv -> {
            Message m = mwv.message();
            addPercept(agent, createLiteral("message",
                createNumber(m.id),
                createString(m.author),
                createString(m.content),
                createNumber(m.original),
                createNumber(m.timestamp)
            ));
            m.reactions.forEach(r -> addPercept(agent, createLiteral("reaction",
                createNumber(m.id),
                createString(r.author()),
                createString(r.reaction())
            )));
            if (includePublicVars) {
                mwv.publicVars().forEach((key, value) ->
                    addPercept(agent, createLiteral("message_var",
                        createNumber(m.id),
                        createString(key),
                        JavaToJasonTranslator.objectToTerm(value)
                    ))
                );
            }
        });

        List<Term> ids = messages.stream()
            .map(mwv -> (Term) createNumber(mwv.message().id))
            .toList();
        addPercept(agent, createLiteral("feed_order", createList(ids)));
    }

    private boolean createPost(String agent, Structure action) {
        List<String> topics = JasonToJavaTranslator.translateTopics(action.getTerm(0));
        Map<String, Object> variables = JasonToJavaTranslator.translateVariables(action.getTerm(1));
        String messageContent = JasonToJavaTranslator.translateString(action.getTerm(2));
        contentManager.addMessage(agent, messageContent, topics, variables);
        return true;
    }

    private boolean repost(String agent, Structure action) {
        int originalId = JasonToJavaTranslator.translateInt(action.getTerm(0));
        contentManager.repost(agent, originalId);
        return true;
    }

    private boolean comment(String agent, Structure action) {
        int originalId = JasonToJavaTranslator.translateInt(action.getTerm(0));
        List<String> topics = JasonToJavaTranslator.translateTopics(action.getTerm(1));
        Map<String, Object> variables = JasonToJavaTranslator.translateVariables(action.getTerm(2));
        String messageContent = JasonToJavaTranslator.translateString(action.getTerm(3));
        contentManager.addMessage(agent, messageContent, topics, variables, originalId);
        return true;
    }

    private boolean react(String agent, Structure action) {
        int originalId = JasonToJavaTranslator.translateInt(action.getTerm(0));
        String reaction = JasonToJavaTranslator.translateString(action.getTerm(1));
        contentManager.addReaction(originalId, agent, reaction);
        return true;
    }

    private boolean createLink(String agent, Structure action) {
        String to = JasonToJavaTranslator.translateString(action.getTerm(0));
        networkManager.addEdge(agent, to);
        addPercept(agent, createLiteral("follows", createString(to)));
        addPercept(to, createLiteral("followed_by", createString(agent)));
        return true;
    }

    private boolean removeLink(String agent, Structure action) {
        String to = JasonToJavaTranslator.translateString(action.getTerm(0));
        networkManager.removeEdge(agent, to);
        removePercept(agent, createLiteral("follows", createString(to)));
        removePercept(to, createLiteral("followed_by", createString(agent)));
        return true;
    }

    private boolean ask(String agent, Structure action) {
        try {
            Literal queryLiteral = (Literal) action.getTerm(0);
            List<Literal> results = knowledgeManager.query(queryLiteral);
            results.forEach(fact -> addPercept(agent, fact));
        } catch (Exception e) {
            System.out.println("Knowledge query failed for agent " + agent + ": " + e.getMessage());
        }
        return true;
    }

    private boolean readPublicProfile(String agent, Structure action) {
        String requestedAgent = JasonToJavaTranslator.translateString(action.getTerm(0));
        Map<String, String> profile = publicProfiles.get(requestedAgent);
        if (profile != null) {
            profile.forEach((attribute, value) ->
                addPercept(agent, createLiteral("public_profile",
                    createString(requestedAgent),
                    createString(attribute),
                    createString(value)
                ))
            );
        }
        return true;
    }
}