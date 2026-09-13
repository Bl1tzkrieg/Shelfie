import coreWebVitals from "eslint-config-next/core-web-vitals"
import typescript from "eslint-config-next/typescript"

// eslint-config-next 16 ya publica flat config, así que no hace falta FlatCompat.
const config = [
  ...coreWebVitals,
  ...typescript,
  {
    ignores: [
      "node_modules/**",
      ".next/**",
      "out/**",
      // Código generado por shadcn/ui: no se audita.
      "components/ui/**",
      "hooks/use-toast.ts",
    ],
  },
  {
    rules: {
      /*
       * Las pantallas cargan sus datos con un efecto de montaje que llama a una
       * función async: el setState ocurre después del primer `await`, nunca de
       * forma síncrona. La regla no distingue ese caso y marca cada llamada, así
       * que se deja como aviso en lugar de error.
       */
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]

export default config
