package bb;

import jason.asSemantics.*;
import jason.asSyntax.*;
import jason.bb.DefaultBeliefBase;
import jason.JasonException;

public class NoRemoveBeliefBase extends DefaultBeliefBase {

    @Override
    public boolean remove(Literal b) {
        // Do nothing, just return false or true depending on your needs
        System.out.println("\nAttempted to remove: " + b + " but ignored. \n");
        return true; // or true if you want to simulate removal success
    }

    @Override
    public boolean add(Literal bel) throws JasonException { 
        System.out.println("\n Added: " + bel + "\n");
        return super.add(bel);
    }
}
