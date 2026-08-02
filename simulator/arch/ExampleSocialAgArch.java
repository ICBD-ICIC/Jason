package arch;

import jason.architecture.AgArch;
import jason.asSyntax.Term;
import java.util.*;

public class ExampleSocialAgArch extends AgArch implements SocialAgArch {

    @Override
    public String createContent(Term source, Term target) {
        return "Las imágenes de las inundaciones son devastadoras, "
             + "pero lo más preocupante es saber que esto ya no es un hecho aislado. "
             + "Familias perdiéndolo todo y ecosistemas destruidos. "
             + "El cambio climático está aquí y la inacción nos está costando caro. "
             + "¿Qué más tiene que pasar para que reaccionemos? 🌧️💔 "
             + "#CambioClimático #Inundaciones #Concienciación #CrisisClimática";
    }

    @Override
    public Map<String, Object> interpretContent(Term content) {
        return null;
    }

}