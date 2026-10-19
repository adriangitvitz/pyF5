# PyF5

[English](README.md) | Español

SDK de Python de solo lectura para F5 BIG-IP. Convierte la API iControl REST en objetos tipados y análisis listos para usar. Los equipos de redes y operaciones pueden responder preguntas como estas sin recorrer la GUI ni leer syslog crudo: qué certificados vencen pronto y qué servicios afectan, qué se cayó en la noche y por qué, y si los clientes están rechazando un certificado nuevo.

## Demo

```python
from datetime import datetime, timedelta, timezone

from pyf5 import F5Client, outages, virtual_servers_by_pool

with F5Client.from_keychain("prod-internal") as f5:
    print(f5.get_devices().current.failover_state)

    vs_by_pool = virtual_servers_by_pool(f5.get_virtual_servers(), f5.get_pools(), f5.get_rules())
    end = datetime.now(timezone.utc)
    entries = f5.get_logs("ltm", end - timedelta(days=1), end).entries

for o in outages(entries, vs_by_pool):
    print(o["pool"], o["member"], o["virtual_servers"], o["down_at"], o["up_at"], o["last_error"])
```

```text
active
/Common/app-a_pool  /Common/node-12:8443  ['app-a_vs']  11:00  11:59  Response Code: 200 (OK)
/Common/api_pool_a  /Common/node-21:2525  ['api_vs']    10:59  12:00  Response Code: 301 (Moved Permanently)
/Common/ldap_pool   /Common/node-31:6803  ['ldap_vs']   11:05  11:56  Unable to connect.
```

Resumen de logs agrupados por patrón de mensaje:

```text
   18 err     tmm    No members available for pool <obj>                ['/Common/api_pool_a', '/Common/app-a_pool', ...]
   20 notice  mcpd   Pool <obj> member <obj> monitor status down.        ['/Common/app-a_pool', '/Common/node-12:8443', ...]
    9 notice  mcpd   SNMP_TRAP: Virtual <obj> has become unavailable     ['/Common/app-a_vs', '/Common/api_vs', ...]
   14 notice  tmm    Clock advanced by <n> ticks                         []
```

Alertas TLS por virtual server:

```text
portal_vs                                48=    0 46=    8 hs=     8
web_vs                                   48=    0 46=    0 hs=   121
log throttled 4 times: counts are minimums
```

## Por qué PyF5

Un BIG-IP ya tiene todo lo necesario para explicar un incidente. El problema es que la información está repartida en objetos que solo tienen sentido juntos:
- una línea de log menciona un pool member;
- el member pertenece a un pool;
- una iRule elige ese pool;
- un virtual server ejecuta la iRule.

Con los certificados pasa igual: los usan perfiles SSL, y esos perfiles están asignados a virtual servers.

PyF5 conecta esas piezas por ti:

- **Tipado, no crudo.** Cada respuesta se valida contra un modelo de pydantic, así que trabajas con `pool.members`, `cert.expires_at` y `entry.severity` en lugar de diccionarios anidados.
- **Relaciones incluidas.**
  - Certificado a perfil a virtual server.
  - Pool a virtual server, por el pool por defecto o por cualquier iRule que lo nombre.
  - Línea de log a virtual server.
- **El análisis junto a los datos.** El parseo de logs, la agregación, el emparejamiento de caídas, el conteo de alertas TLS y el inventario de certificados son funciones simples sobre los modelos. Se pueden combinar en un notebook, un script u otro servicio.
- **Solo lectura por diseño.** Solo hace peticiones `GET`, así que es seguro apuntarlo a producción.
- **Cuidadoso con el equipo.**
  - Rate limit con token bucket y circuit breaker.
  - Reintentos con backoff exponencial ante errores de red y 5xx.
  - Revocación del token al salir.

## Funcionalidades

### Configuración y estado

| Método | Regresa |
|---|---|
| `get_virtual_servers()` / `get_virtual_server(name)` | Virtual servers con destino, pool por defecto, iRules y perfiles |
| `get_virtual_servers_stats()` | Estadísticas de tráfico por virtual server |
| `get_pools()` | Pools con sus members y el estado de cada uno (`pool.members`) |
| `get_nodes()` | Nodos con estado y sesión |
| `get_monitors(type)` / `get_all_monitors()` | Monitores HTTP, HTTPS y TCP con `send`, `recv`, `interval` y `timeout`, indexados por ruta completa |
| `get_rules()` | iRules con su definición |
| `get_certificates()` | Certificados con subject, issuer, SAN y vencimiento |
| `get_ssl_profiles(type)` | Perfiles client-SSL y server-SSL y los certificados que usan |
| `get_devices()` | Equipos del clúster. `.current` indica si estás hablando con el equipo activo o el standby |
| `get_logs(facility, start, end)` | Cualquier facility de logs (`ltm`, `audit`, ...) en un rango de tiempo, parseada en objetos `LogEntry` mediante `.entries` |

### Análisis

| Función | Qué responde |
|---|---|
| `pyf5.filter_entries(entries, min_severity, text)` | Solo las líneas con cierta severidad o mayor, o que contienen un texto |
| `pyf5.aggregate(entries)` | Qué patrones de mensaje se repiten, cuántas veces, desde cuándo hasta cuándo y sobre qué objetos |
| `pyf5.outages(entries, vs_by_pool)` | Qué pool members se cayeron, por cuánto tiempo, con qué error de monitor y qué virtual servers se vieron afectados |
| `pyf5.tls_alerts(entries, virtual_servers)` | Qué virtual servers tienen clientes que rechazan el certificado (alertas 46 y 48) o que fallan el handshake |
| `pyf5.virtual_servers_by_pool(vs, pools, rules)` | Qué virtual servers usan cada pool, por el pool por defecto o por una iRule |
| `pyf5.certs.retrieve_inventory(f5)` / `filter_inventory(...)` / `flatten(...)` | Qué certificados vencen en N días y qué perfiles y virtual servers dependen de ellos |
| `pyf5.report.pool_health(f5)` / `summarize(data)` | Salud de los pools por virtual server: members arriba y abajo, y porcentaje de salud |

## Inicio rápido

1. Instala el SDK (requiere Python 3.9 o mayor):

   ```bash
   uv add git+https://github.com/adriangitvitz/pyF5.git
   # o: pip install git+https://github.com/adriangitvitz/pyF5.git
   ```

2. Configura las credenciales con una de estas dos opciones.

   Exporta variables de entorno:

   ```bash
   export F5_HOST=<management-host> F5_USERNAME=<username> F5_PASSWORD=<password>
   ```

   O, en macOS, guarda un elemento del Keychain por equipo:
   - el servicio es `pyf5.<ambiente>`;
   - la cuenta es el usuario;
   - el comentario es el host de administración;
   - `-w` pide el password de forma interactiva.

   ```bash
   security add-generic-password -s pyf5.prod-internal -a <username> -j <management-host> -w
   ```

3. Consulta el equipo:

   ```python
   from pyf5 import F5Client

   with F5Client.from_env() as f5:  # o F5Client.from_keychain("prod-internal")
       device = f5.get_devices().current
       print(device.name, device.failover_state, device.version)
       for vs in f5.get_virtual_servers().items:
           print(vs.name, vs.destination, vs.pool)
   ```

## Uso y configuración

### Crear un cliente

```python
from pyf5 import F5Client, RateLimitConfig

f5 = F5Client(host=host, username=username, password=password)
f5 = F5Client.from_env()
f5 = F5Client.from_keychain("prod-internal")
```

Las tres formas aceptan las mismas opciones:

```python
F5Client.from_env(
    rate_limit_config=RateLimitConfig(requests_per_second=5.0, burst_capacity=10),
    timeout=30,      # segundos por petición; súbelo para rangos de logs largos
    max_retries=3,   # aplica a errores de red y 5xx; los 4xx fallan de inmediato
)
```

Usa el cliente como context manager (`with ... as f5:`) o llama tú a `f5.close()`. En ambos casos se revoca el token en el equipo y se cierra la conexión.

### Errores

| Excepción | Cuándo |
|---|---|
| `pyf5.AuthenticationError` | El equipo rechaza las credenciales o no regresa un token |
| `pyf5.CircuitOpenError` | Demasiadas fallas seguidas; las peticiones se pausan 60 segundos |
| `httpx.HTTPStatusError` | La API responde 4xx, o 5xx después de agotar los reintentos |
| `httpx.TransportError` | No se alcanza el equipo después de agotar los reintentos |

### Logs

`get_logs` recibe datetimes con zona horaria y los convierte a UTC para la API:

```python
from datetime import datetime, timedelta, timezone

from pyf5 import aggregate, filter_entries, tls_alerts

end = datetime.now(timezone.utc)
entries = f5.get_logs("ltm", end - timedelta(hours=1), end).entries

for line in filter_entries(entries, text="pool"):
    print(line.raw)

for g in aggregate(filter_entries(entries, min_severity="warning")):
    print(g["count"], g["severity"], g["pattern"], g["objects"][:3])

result = tls_alerts(entries, f5.get_virtual_servers())
```

Los niveles de severidad van de `emerg` a `debug`. Los cambios de estado de los pool members se registran como `notice`, así que usa `min_severity="notice"` cuando busques caídas.

### Monitores

```python
monitors = f5.get_all_monitors()
for pool in f5.get_pools().items:
    m = monitors.get(pool.monitor)
    print(pool.name, m.recv if m else pool.monitor)
```

### Certificados y salud de pools

```python
from pyf5.certs import filter_inventory, retrieve_inventory
from pyf5.report import pool_health, summarize

expiring = filter_inventory(retrieve_inventory(f5), days=30, in_use=True)
rows = summarize(pool_health(f5))
```

### Ejemplos

En `examples/` hay scripts listos para correr. Todos reciben `--env`, que es el nombre del elemento en el Keychain:

| Script | Salida |
|---|---|
| `examples/certificate_inventory.py --env <env> --days 30 --in-use` | `certs/<env>_certificates.json` y `.csv`, más un reporte en consola |
| `examples/pool_health.py --env <env>` | `<env>_output.json` y `<env>_summary.csv` |
| `examples/outages.py --env <env> --hours 24` | Caídas con duración, error de monitor y virtual servers afectados |
| `examples/log_summary.py --env <env> --hours 1` | Patrones de logs y alertas TLS por virtual server |

```bash
uv run python examples/outages.py --env prod-internal
```

### Estructura del proyecto

```text
pyf5/
  base.py          F5Client: autenticación, reintentos, rate limit, circuit breaker, métodos de la API
  logs.py          filtrado, agregación, caídas y alertas TLS sobre los logs
  topology.py      relación pool a virtual server (pool por defecto e iRules)
  certs.py         inventario de certificados
  report.py        salud de pools por virtual server
  credentials.py   lectura del Keychain de macOS
  schemas/         modelos de pydantic para cada respuesta
examples/          scripts ejecutables construidos sobre el SDK
```
