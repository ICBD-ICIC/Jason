/* ==========================================================
    Available Environment Actions

    updateFeed
    updateFeed(+IncludePublicVars)
        IncludePublicVars: boolean (optional, default false)
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)
                        message_var(+Id, +Key, +Value)  [only if IncludePublicVars = true]

    searchContent(+Topic)
    searchContent(+Topic, +IncludePublicVars)
        Topic: string/atom
        IncludePublicVars: boolean (optional, default false)
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)
                        message_var(+Id, +Key, +Value)  [only if IncludePublicVars = true]

    searchAuthor(+Author)
    searchAuthor(+Author, +IncludePublicVars)
        Author: string/atom
        IncludePublicVars: boolean (optional, default false)
        Percepts added: message(+Id, +Author, +Content, +Original, +Timestamp)
                        reaction(+Id, +Author, +Reaction)
                        feed_order(+Ids)
                        message_var(+Id, +Key, +Value)  [only if IncludePublicVars = true]

    createPost(+Topics, +Variables, +Content)
        Topics: list of strings/atoms, e.g. [tech, news, "floods"]
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    repost(+Id)
        Id: number

    comment(+Id, +Topics, +Variables, +Content)
        Id: number
        Topics: list of strings/atoms, e.g. [tech, news, "floods"]
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    react(+Id, +Reaction)
        Id: number
        Reaction: string/atom, e.g. like or "love"

    ask(+Query)
        Queries the common knowledge base.
        Query: any knowledge literal, e.g. weather(london, W)
        Percepts added: grounded literals matching the query, e.g. weather(london, sunny)

    createLink(+Agent)
        Agent: string/atom
        Percepts added: follows(Agent) for self        
                        followedBy(Self) for target

    removeLink(+Agent)
        Agent: string/atom
        Percepts removed: follows(Agent) for self
                          followedBy(Self) for target

    readPublicProfile(+Agent)
        Agent: string/atom 
        Percepts added: public_profile(Agent, Attribute, Value)
========================================================== */

/* ==========================================================
   Available Internal Actions

    ia.createContent(+Topic, +Variables, -Content)
        Topic: string/atom
        Variables: map of key(value) pairs, e.g. [sentiment(negative), ...]
        Content: string

    ia.interpretContent(+Content, -Interpretation)
        Content: string
        Interpretation: map of key(value) pairs, e.g. [sentiment(negative), ...]
========================================================== */
cycle(0).

!start.

+!start: true <- 
    ask(some_fact(A, B));
    readPublicProfile("Alice");
    createLink("dummy");
    updateFeed.

+some_fact(A, B): true <- 
    .print("Received some_fact with A=", A, " and B=", B).

+follows(Agent): true <- 
    .print("Now following ", Agent).

+followedBy(Agent): true <- 
    .print("Now followed by ", Agent).

+public_profile(Agent, Key, Value): true <- 
    .print("Public profile of ", Agent, ": ", Key, " = ", Value).

+feed_order([Id|Ids]): cycle(0) <- 
    -+cycle(1);
    .wait(message(Id, Author, Content, Original, Timestamp));
    .print("New message from ", Author, ": ", Content, " (Original: ", Original, ", Timestamp: ", Timestamp, ")");
    ia.interpretContent(Content, Interpretation);
    .print("Interpreted content: ", Interpretation);
    Topics = [floods, "climate change awareness"];
    Variables = [sentiment(positive), emotion("worry")];
    ia.createContent(Topics, Variables, CommentContent);
    createPost(Topics, Variables, CommentContent);
    comment(Id, Topics, Variables, CommentContent);
    repost(Id);
    react(Id, like);
    searchAuthor(Author);
    searchContent(example);
    .wait(10000);
    searchAuthor(social_agent).

+reaction(Id, Author, Reaction): true <- 
    .print("New reaction from ", Author, ": ", Reaction, " on message ", Id).

+feed_order(FeedList): cycle(1) <- 
    !collect_messages(FeedList, "", Conversation);
    .print(Conversation).

+!collect_messages([] , Conversation, Conversation) : true <- true.

+!collect_messages([ID|Tail], Conversation, Result) : true <-
    .wait(message(ID, Author, Content, _, _));
    .concat("\n@", Author, ": ", Content, Post);
    .concat(Post, Conversation, UpdatedConversation);
    !collect_messages(Tail, UpdatedConversation, Result).
