#!/bin/python3
# -*- coding: utf-8 -*-

import os
import math
import re
import time
import datetime
import math
import random
import csv
import json
import xml.etree.ElementTree as ET
import requests

LIMPIAR_PANTALLA = "clear"

# Definimos las rutas de archivo
RUTA_DATOS_GTFS = os.path.join(os.path.dirname(__file__), "datos/gtfs")
CONJUNTOS_GTFS = os.listdir(RUTA_DATOS_GTFS)
RADIO_BUSQ_PREDET = 0.0005
SEG_DESCANSO_ENTRE_PETIC = 0.125
SEG_DESCANSO_ENTRE_FALLOS = 1.5
INTENTOS_MAX = 2
NUM_PRECISION_COORD = 6

SERVIDORES_OSM_OVERPASS = [
    "https://overpass.kumi.systems/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
    "http://overpass.openstreetmap.ru/cgi/",
    # "https://lz4.overpass-api.de/api",
]

urlServidorOsmOverpass = None
limitePeticionesAlcanzado = False

# Contiene "agencias" que son básicamente las subdivisones
# del transporte, en este caso macro, tren, sitren, etc
agency = {}
# Contiene las rutas como tal. Es recomendable obtener las
# rutas que contengan el nombre de una agencia determinada,
# para filtrar y simplificar la navegación
routes = {}
# Contiene los viajes que realiza la ruta, es decir, cosas
# como la dirección y sentido, los días, y un identificador
# para las paradas que se reaizan
trips = {}
# Contiene los tiempos de de frecuencia, esto es, la hora
# en la que comienza y termina la circulación de la ruta.
frequencies = {}
# Describe la forma que recorre la ruta, por ejemplo,
# para delinearla en un mapa
shapes = {}
# Contiene las ubicaciones de las paradas, no sirve sin
# stop_times
stops = {}
# Contiene las paradas específicas de un viaje en particular.
# Referencia a stops
stop_times = {}


def csv2dict(file):
    """Tranforma datos crudos CSV a una lista de diccionarios
    tomando como claves la primera columna del CSV"""
    with open(file) as f:
        reader = csv.DictReader(f)
        datos = [x for x in reader]

    return datos


def sinput(texto: str = "",
           msjError: str = "Dato inválido, intenta de nuevo",
           tipoClase: any = str,
           rangoValido: tuple = ()):
    """
    Solicita datos al usuario, con diversas validaciones a prueba de tontos.
    @texto: El texto a imprimir antes de solicitar la entrada
    @type: El tipo al que intentar convertir el dato.
           Si esto falla se retorna el dato como cadena
    @range: Puede ser una tupla con 2 números, el primero menor y
            el segundo mayor, para comparar valores numéricos (inclusivo).
            También se puede entregar una tupla con los valores
            a tratar como válidos, y, de no obtener alguno dentro
            del rango, volver a preguntar al usuario hasta obtener
            un valor válido.
    """
    datos = None
    esLaEntradaValida = False
    while not esLaEntradaValida:
        try:
            datos = input(texto)
            if len(rangoValido) > 0:
                if len(rangoValido) == 2 and \
                        isinstance(rangoValido[0], int) and \
                        isinstance(rangoValido[1], int):
                    datos = tipoClase(datos)
                    if rangoValido[0] <= datos <= rangoValido[1]:
                        esLaEntradaValida = True
                else:
                    if datos in rangoValido:
                        esLaEntradaValida = True
            else:
                esLaEntradaValida = True
            datos = tipoClase(datos)
            if not esLaEntradaValida:
                print(msjError)
        except (KeyboardInterrupt, EOFError):
            print()
            exit()
        except ValueError:
            print("Intenta nuevamente.")
        else:
            if esLaEntradaValida:
                return datos


def pausa(texto: str = "Presiona Entrar para continuar..."):
    try:
        input(texto)
    except (KeyboardInterrupt, EOFError):
        print()
        exit()


def limpiarPantalla():
    os.system(LIMPIAR_PANTALLA)


def listar(entradas,
           texto: str = "Listando:",
           pausarEntreEntradas=False,
           pausaFinal=True):
    print(texto)

    for i, entrada in enumerate(entradas, 1):
        num = str(i).rjust(len(str(len(entradas))), "0")
        print(f"{num}) {entrada}", end="")
        if pausarEntreEntradas:
            pausa("")
        else:
            print()

    print("Terminado.")

    if pausaFinal:
        pausa()


def mostrarMenu(entradas: list,
                texto: str = "Elige una opción:",
                mostrarOpcionSalir=True):
    print(texto)
    entradas = list(entradas)

    if mostrarOpcionSalir:
        entradas.append("Salir")

    for i, entrada in enumerate(entradas, 1):
        num = str(i).rjust(len(str(len(entradas))), "0")
        print(f"{num}) {entrada}")


def obtenerAgencias(archivoAgency):
    agencies = {}
    datos = csv2dict(archivoAgency)

    for agency in datos:
        agency_id = agency["agency_id"]

        if not agencies.get(agency_id):
            agencies[agency_id] = {}

        agencies[agency_id] = agency

    return agencies


def obtenerRutas(archivoRoutes, quitarTexto=False):
    routes = {}
    datos = csv2dict(archivoRoutes)

    for route in datos:
        agency_id = route["agency_id"]
        route_id = route["route_id"]

        if quitarTexto:
            route["route_long_name"] = re.sub("^Troncal|^Alimentadora|^Complement\w+a", "", route["route_long_name"])

        route["route_long_name"].strip()

        route["route_type"] = int(route["route_type"])

        if not routes.get(agency_id):
            routes[agency_id] = {}

        if not routes[agency_id].get(route_id):
            routes[agency_id][route_id] = {}

        if not route["route_color"]:
            route["route_color"] = "FFFFFF"
        if not route["route_text_color"]:
            route["route_text_color"] = "000000"

        routes[agency_id][route_id] = route

    return routes


def obtenerViajes(archivoTrips):
    trips = {}
    datos = csv2dict(archivoTrips)

    for trip in datos:
        route_id = trip["route_id"]
        trip_id = trip["trip_id"]

        if not trips.get(route_id):
            trips[route_id] = {}

        trips[route_id][trip_id] = trip

    return trips


def obtenerParadas(archivoStops):
    stops = {}
    datos = csv2dict(archivoStops)

    for i, stop in enumerate(datos):
        stop_id = stop["stop_id"]
        stop["index"] = i

        if not stops.get(stop_id):
            stops[stop_id] = {}

        stops[stop_id] = stop

    return stops


def obtenerHorariosDeParada(archivoStopTimes):
    stimes = {}
    datos = csv2dict(archivoStopTimes)

    for stop in datos:
        trip_id = stop["trip_id"]

        if not stimes.get(trip_id):
            stimes[trip_id] = []

        stimes[trip_id].append(stop)

    return stimes


def obtenerFrecuencias(archivoFrequencies):
    frequencies = {}
    datos = csv2dict(archivoFrequencies)

    for trip in datos:
        trip_id = trip["trip_id"]

        if not frequencies.get(trip_id):
            frequencies[trip_id] = []

        trip["headway_secs"] = int(trip["headway_secs"])

        frequencies[trip_id].append(trip)

    return frequencies


def obtenerHoraDeInicioYDelta(parada, frecuencia):
    # Truco para obtener el tiempo en enteros en una lista de hora (1), minuto (2) y segundo (3)
    # Necesitamos los tiempos de inicio y fin para calcular cuántas iteraciones haremos
    # Dicho de otra forma, cuántas veces cabe la frecuencia en los tiempos de inicio y fin
    horaIniParadaStr = [
        int(x) for x in parada["stop_times"]["arrival_time"].split(":")]
    horaIniStr = [
        int(x) for x in frecuencia["start_time"].split(":")]
    horaFinStr = [int(x)
                  for x in frecuencia["end_time"].split(":")]

    # Convertimos a segundos para el cálculo
    horaIniParadaInt = (
        horaIniParadaStr[0] * 60 * 60) + (horaIniParadaStr[1] * 60) + horaIniParadaStr[2]
    horaIniInt = (
        horaIniStr[0] * 60 * 60) + (horaIniStr[1] * 60) + horaIniStr[2]
    horaFinInt = (
        horaFinStr[0] * 60 * 60) + (horaFinStr[1] * 60) + horaFinStr[2]

    # ¿Cuántas frecuencias se necesitan para llevar a un pasajero?
    # Ninguna, porque el pasajero se va en coche >:(
    iteraciones = (
        horaFinInt - horaIniInt) // frecuencia["headway_secs"]
    # Creamos una lista de x de deltas del tamaño de la frecuencia,
    # donde x es la cantidad de veces que cupo la frecuenca
    minutos = [
        datetime.timedelta(seconds=float(
            frecuencia["headway_secs"]))
        for x in range(iteraciones)
    ]

    # Esto para agregar las deltas a este punto (horaInicio + (delta * iteración))
    # horaInicioDateTime = datetime.time(horaIniStr[0], horaIniStr[1], horaIniStr[2])
    horaInicioDateTime = datetime.datetime.strptime(
        frecuencia["start_time"], "%H:%M:%S")
    deltaPosicionParada = datetime.timedelta(
        seconds=float(horaIniParadaInt))

    return horaInicioDateTime, deltaPosicionParada, minutos


def obtenerTrazos(archivoShapes):
    """Devuelve los trazos de ruta ordenados en un diccionario por id de
    trazo (shape_id) y número de secuencia (shape_pt_sequence)"""
    shapes = {}
    datos = csv2dict(archivoShapes)

    for trace in datos:
        shape_id = trace["shape_id"]

        if not shapes.get(shape_id):
            shapes[shape_id] = {}

        pt_seq = int(trace.pop("shape_pt_sequence"))
        shapes[shape_id][pt_seq] = trace

    return shapes


def cambiarUrlServidorOverpass(quitarActual=False):
    global urlServidorOsmOverpass
    urlActual = urlServidorOsmOverpass
    huboExito = False # Para informar si se tuvo éxito en la selección y dejar que main() (o lo que sea) decida qué hacer
    seleccionandoServidor = True # Bandera

    # Copiamos la lista
    servidoresDisponibles = list(SERVIDORES_OSM_OVERPASS)

    if quitarActual:
        try:
            servidoresDisponibles.remove(urlActual)
        except ValueError:
            pass

    while seleccionandoServidor:
        # Si hay servidores disponibles...
        if servidoresDisponibles:
            # Elegimos un nuevo servidor al azar
            urlActual = random.choice(servidoresDisponibles)
            print(f'Probando con {urlActual}...')

            try:
                # Preguntamos si no nos han limitado las peticiones de este servidor
                respuesta = requests.get(f"{urlActual}/status")

                # Si el límite es 0 (ninguno), establecemos, salimos del bucle,
                # e informamos del éxtio
                if "Rate limit: 0" in respuesta.text:
                    print(f'{urlActual} ha sido seleccionado.')
                    urlServidorOsmOverpass = urlActual
                    huboExito = True
                    seleccionandoServidor = False

                else:
                    print(f'Puede que nos hayan limitado. Respuesta del servidor:\n')
                    print(respuesta.text)
                    print()
                    servidoresDisponibles.remove(urlActual)
                    print("Saltando...")

            except Exception:
                # Posiblemente error de conexión, no podemos proseguir
                import traceback
                print("Se ha producido un error intentando conectar. Detalles:")
                print(traceback.format_exc())
                print("No se pudo seleccionar un servidor.")
                seleccionandoServidor = False
                continue


        # Peor de los casos, nos limitaron en todos los servidores :/
        else:
            print("No se encontraron instancias disponibles por el momento.\n")
            print("Intenta más tarde o agrega una nueva instancia al código fuente")
            seleccionandoServidor = False

    return huboExito


def consultaOverpass(peticion: str):
    respuesta = None
    while respuesta is None:
        # Por si llamamos directamente a la función y el servidor aún no está definido
        global urlServidorOsmOverpass
        if not urlServidorOsmOverpass:
            # Si no hay servidor de OSM disponible, no tiene setido seguir
            hayServidor = cambiarUrlServidorOverpass()
            if not hayServidor:
                pausa("Presiona Entrar para volver...")
                respuesta = ""
                continue

        urlPeticion = f'{urlServidorOsmOverpass}/interpreter'

        datos = requests.post(urlPeticion, data={"data": peticion})

        if "rate_limited" in datos.text:
            print("Se alcanzó el límite de peticiones de esta IP, tenemos problemas...")
            print("Intentando cambiar de servidor...")
            limitePeticionesAlcanzado = not cambiarUrlServidorOverpass()

            if limitePeticionesAlcanzado:
                print("No hubo éxito tratando de cambiar de servidor. Abortando...")
                respuesta = ""
                continue

        respuesta = datos.text
    return respuesta


def dividirRuta(ruta):
    componentesRuta = []
    texto = str()

    if not isinstance(ruta, (str, dict)):
        return componentesRuta
    
    if isinstance(ruta, dict):
        ruta = ruta["route_id"]

    for letra in ruta:
        if letra == "-":
            if len(componentesRuta) < 2:
                texto = int(texto) if texto.isnumeric() else texto

            componentesRuta.append(texto)
            texto = str()

            continue

        elif texto.isnumeric() and letra.isalpha():
            if len(componentesRuta) < 2:
                texto = int(texto)

            componentesRuta.append(texto)
            texto = str()

        elif texto.isalpha() and letra.isnumeric():
            componentesRuta.append(texto)
            texto = str()

        texto += letra

    if len(componentesRuta) < 2:
        texto = int(texto) if texto.isnumeric() else texto

    componentesRuta.append(texto)

    return componentesRuta


def ordenarParadas(horarioParadas):
    # Obtenemos las paradas asociadas al id de parada
    paradas = [stops[x["stop_id"]] for x in horarioParadas]
    # Mezclamos ambos datos en una lista con ambos diccionarios (es más útil tener los datos de paradas juntos)
    paradas = [{"stops": x, "stop_times": y}
               for x, y in zip(paradas, horarioParadas)]
    # Ordenamos
    paradas = sorted(paradas, key=lambda p: int(
        p["stop_times"]["stop_sequence"]))
    return paradas


def ajustarHorariosDeParadas(paradas: list):
    # Obtenemos una copia de la lista
    paradas = list(paradas)

    # Obtenemos la diferencia entre la hora de la primera parada y 00:00 (puede no haberla)
    horaIniStr = [int(x) for x in paradas[0]
                  ["stop_times"]["arrival_time"].split(":")]
    delta = datetime.timedelta(seconds=float(
        (horaIniStr[0] * 60 * 60) + (horaIniStr[1] * 60) + horaIniStr[2]))

    # Quitamos la delta que pudiese tener (si las paradas comienzan en 00:00 no se modificará nada)
    for i, p in enumerate(list(paradas)):
        p = p["stop_times"]
        hora = datetime.datetime.strptime(
            p["arrival_time"], "%H:%M:%S") - delta
        p["arrival_time"] = hora.strftime("%H:%M:%S")
        paradas[i]["stop_times"] = p

    return paradas


def verificarColisionesDeParadasGtfsConOsm(
            paradas: list,
            ruta: dict,
            agencia: dict,
            radio: int = RADIO_BUSQ_PREDET,
            generarReporte = False,
            incluirRespuestaCruda = False,
            pausarAlFinalizar = True,
            mostrarProgreso = True):
    global limitePeticionesAlcanzado
    # Si no hay servidor de OSM disponible, no tiene setido seguir
    hayServidor = cambiarUrlServidorOverpass()

    if not hayServidor:
        pausa("Presiona Entrar para volver...")
        return

    rutaResultadosColisiones = "~/Resultados_colisiones_{}-{}.json"
    rutaResultadosColisiones = rutaResultadosColisiones.format(
        agencia["agency_id"], ruta["route_short_name"]
    )
    rutaResultadosColisiones = os.path.expanduser(rutaResultadosColisiones)

    try:
        resultados = {
            "coord": "",
            "collisions": {},
            "credits": "",
            "timestamp": "",
        }

        peticionQl  = "[out:json];"
        peticionQl  += "("

        for i, p in enumerate(paradas, 1):
            if mostrarProgreso:
                print(f'Procesando parada {i} - {p["stops"]["stop_name"]}...')

            # Por si acaso redondeemos X, Y, y el radio a 6 dígitos
            latitud = round(float(p["stops"]["stop_lat"]), NUM_PRECISION_COORD)
            longitud = round(float(p["stops"]["stop_lon"]), NUM_PRECISION_COORD)
            radio = round(float(radio), NUM_PRECISION_COORD)

            norte = round(latitud - radio, NUM_PRECISION_COORD)
            sur = round(latitud + radio, NUM_PRECISION_COORD)
            este = round(longitud - radio, NUM_PRECISION_COORD)
            oeste = round(longitud + radio, NUM_PRECISION_COORD)
            # ref = ref.split("_", 1)[1]
            peticionQl += 'node'
            peticionQl += '[highway=bus_stop]'
            # peticionQl += f'["ref"~"{ref}$"]'
            peticionQl += f'({norte},{este},{sur},{oeste});'

            if mostrarProgreso:
                print(f'Parada {i} - {p["stops"]["stop_name"]} procesada')
        
        peticionQl += ");"
        peticionQl += "out meta;"

        try:
            print('Realizando petición...')
            # Procesamos la respuesta JSON
            respuesta = consultaOverpass(peticionQl)
            datos = json.loads(respuesta)
        except ConnectionError:
            respuesta = ""
            datos = {}
            import traceback
            print('Error:')
            print(traceback.format_exc())

        # Créditos de los datos
        osmCredits = datos.get("osm3s", {}).get("copyright", "")
        # Generamos una marca de tiempo por defecto por si no hubiese
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Obtenemos la marca de tiempo, reemplazando con
        # la hora actual si no hay
        timestamp = datos.get("osm3s", {}).get("timestamp_osm_base", timestamp)

        if datos.get("elements"):
            for paradaGtfs in paradas:
                for nodo in datos["elements"]:
                    nodo = dict(nodo)
                    lat = float(paradaGtfs["stops"]["stop_lat"])
                    lon = float(paradaGtfs["stops"]["stop_lon"])
                    parada = {"attrib": {}, "tags": {}}
                    parada["tags"] = nodo.pop("tags", {})
                    parada["attrib"] = nodo

                    esCercanaLaLat = math.isclose(lat, parada["attrib"]["lat"])
                    esCercanaLaLon = math.isclose(lon, parada["attrib"]["lon"])
                    sonCercanasLasCoord = esCercanaLaLat and esCercanaLaLon
                    if sonCercanasLasCoord or \
                            paradaGtfs["stops"]["stop_id"] == parada["tags"].get("ref"):
                        # Guardamos cada coincidencia en una diccionario por
                        # id de parada para facilitar identificación posterior
                        resultados["collisions"][paradaGtfs["stops"]["stop_id"]] = parada
                    # La razón por la que no podemos verificar colisiones indirectas
                    # es porque no sabemos a qué parada pertenecen dichas colisiones
                    # Sería factible acumular todas las colisiones indirectas bajo una
                    # sola etiqueta para decidir qué hacer con cada una por separado
                    #     resultados["collisions"]["direct"].append(parada)
                    # else:
                    #     resultados["collisions"]["indirect"].append(parada)

        resultados.update({
            "credits": osmCredits,
            "timestamp": timestamp,
        })

        if incluirRespuestaCruda:
            resultados["response"] = respuesta

        if generarReporte:
            print("Intentando guardar resultados...")
            with open(rutaResultadosColisiones, "w") as f:
                f.write(json.dumps(resultados, indent=2))

            print(f"Resultados guardados en {rutaResultadosColisiones}")
        else:
            return resultados

    except (KeyboardInterrupt, EOFError):
        print("\nProceso interrumpido.\n")

    if pausarAlFinalizar:
        pausa()


def verificarColisionDeParadaEnCoordenadas(latitud: float,
                                           longitud: float,
                                           radio=RADIO_BUSQ_PREDET,
                                           incluirRespuestaCruda=False):
    NUM_PRECISION_COORD = 6
    # Por si acaso redondeemos X, Y, y el radio a 6 dígitos
    latitud = round(float(latitud), NUM_PRECISION_COORD)
    longitud = round(float(longitud), NUM_PRECISION_COORD)
    radio = round(float(radio), NUM_PRECISION_COORD)

    norte = round(latitud - radio, NUM_PRECISION_COORD)
    sur = round(latitud + radio, NUM_PRECISION_COORD)
    este = round(longitud - radio, NUM_PRECISION_COORD)
    oeste = round(longitud + radio, NUM_PRECISION_COORD)
    peticionQl  = "node({},{},{},{})[highway=bus_stop];"
    peticionQl += "out meta;"
    peticionQl = peticionQl.format(norte, este, sur, oeste)
    resultados = {
        "coord": "",
        "collisions": {"direct": [], "indirect": []},
        "credits": "",
        "timestamp": "",
    }

    datos = consultaOverpass(peticionQl)

    # La respuesta XML procesada por Python para posterior análisis por este módulo
    xml = ET.fromstring(datos)
    nodos = xml.findall(".//node")
    osmCredits = xml.find(".//note").text
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    timestamp = xml.find(".//meta").get("osm_base", timestamp)

    if nodos:
        for nodo in nodos:
            parada = {"attrib": {}, "tags": {}}
            parada["attrib"] = {str(k): str(v) for k, v in nodo.attrib.items()}
            parada["attrib"].update({
                "lat": float(nodo.get("lat")), "lon": float(nodo.get("lon"))
            })

            for etiqueta in nodo.findall(".//tag"):
                parada["tags"][etiqueta.get("k", "")] = etiqueta.get("v")

            esCercanaLaLat = math.isclose(latitud, parada["attrib"]["lat"])
            esCercanaLaLon = math.isclose(longitud, parada["attrib"]["lon"])
            sonCercanasLasCoordenadas = esCercanaLaLat and esCercanaLaLon
            if sonCercanasLasCoordenadas:
                resultados["collisions"]["direct"].append(parada)

            else:
                resultados["collisions"]["indirect"].append(parada)

    resultados.update({
        "timestamp": timestamp,
        "credits": osmCredits,
        "stop_lat": latitud,
        "stop_lon": longitud,
    })

    if incluirRespuestaCruda:
        resultados["response"] = datos

    return resultados


def generarOsmchange(listaCrear: list, listaModificar: list, listaEliminar: list):
    xml = ET.Element("osmChange", {"version": "0.6", "generator": ""})

    # Creamos los elementos de creación, modificación y
    # eliminación del xml osmChange
    nodoCreate = ET.Element("create")
    nodoModify = ET.Element("modify")
    nodoDelete = ET.Element("delete")

    for listaActual, nodoActual in [(listaCrear, nodoCreate), (listaModificar, nodoModify), (listaEliminar, nodoDelete)]:
        for elemento in listaActual:
            if isinstance(elemento, ET.Element):
                nodoActual.append(elemento)
            else:
                print("Error con", str(elemento))
                print("Tipo de elemento inválido. Saltando...")

    xml.append(nodoCreate)
    xml.append(nodoModify)
    xml.append(nodoDelete)
    xml = ET.ElementTree(xml)

    return xml


def generarOsmchangeDeRutaGtfs(operador: str, agencia: dict, ruta: dict, viaje: dict, paradas: list):
    # Generamos un nombre de ruta
    rutaOsmChange = f'{agencia["agency_id"]}-{ruta["route_short_name"]}_{viaje["trip_headsign"]}.osc'
    # Limpiamos por si acaso
    rutaOsmChange = re.sub("[/\\:><~?!]", "", rutaOsmChange)
    # Agregamos la ruta a la carpeta del usuario como parte de la ruta
    rutaOsmChange = os.path.expanduser(f"~/{rutaOsmChange}")
    obj_id = -1

    # Creamos las listas de los elementos a crear, modificar y eliminar
    elementosACrear = []
    elementosAModificar = []
    elementosABorrar = []

    # Creamos e inicializamos el nodo de relación de ruta
    relacionRuta = ET.Element(
        "relation", {"id": str(obj_id), "version": "1", })
    obj_id -= 1

    # Añadimos las etiquetas correspondientes a la relación de ruta
    tagsRuta = {
        "colour": f'#{ruta["route_color"]}',
        "ref": ruta["route_short_name"],
        "name": f'{ruta["route_short_name"]}: {viaje["trip_headsign"]}',
        "long_name": f'{ruta["route_long_name"].strip()}: {viaje["trip_headsign"]}',
        "type": "route",
        "gtfs_route_text_color": f'#{ruta["route_text_color"]}',
        "gtfs_route_id": ruta["route_id"],
        "gtfs_agency_id": agencia["agency_id"],
        "network": agencia["agency_name"],
        "operator": operador,
        "public_transport:version": "2",
        "source": "https://datos.jalisco.gob.mx",
        "to": viaje["trip_headsign"],
    }

    # Si es 3, es ruta de camión; si es 0, es ruta de tren ligero
    if ruta["route_type"] == 3:
        tagsRuta["route"] = "bus"
    elif ruta["route_type"] == 0:
        tagsRuta["route"] = "light_rail"

    for k, v in list(tagsRuta.items()):
        tag = ET.Element("tag", {
            "k": str(k), "v": str(v)
        })
        relacionRuta.append(tag)

    colisiones = verificarColisionesDeParadasGtfsConOsm(
        paradas, ruta, agencia, pausarAlFinalizar=False, mostrarProgreso=False
    )

    # Iteramos por cada parada para crearla como nodo y
    # añadir el nodo a la relación de ruta
    offset = -obj_id
    for i, parada in enumerate(paradas, (-obj_id)+1):
        lat = float(parada["stops"]["stop_lat"])
        lon = float(parada["stops"]["stop_lon"])

        print(f"Procesando parada #{i-offset}")

        colision = colisiones["collisions"].get(parada["stops"]["stop_id"])

        # Modificamos una parada existente
        if colision is not None:
            print(f"Procesando colisión de parada directa...")

            # Creamos el nodo
            for k in ["user", "changeset", "timestamp", "uid"]:
                colision["attrib"].pop(k)

            atributosNodoParada = {
                str(k): str(v) for k, v in colision["attrib"].items()
            }
            nodoParada = ET.Element("node", atributosNodoParada)

            # Añadimos las etiquetas al nodo
            tagsParada = colision["tags"]
            tagsParada.update({
                "bus": "yes",
                "highway": "bus_stop",
                "name": parada["stops"]["stop_name"],
                "public_transport": "platform",
                "ref": parada["stops"]["stop_id"],
                "gtfs_id": parada["stops"]["stop_id"],
            })

            # Buscamos si el nodo de colisión ya tenía las sig. etiquetas que queremos establecer
            # Les añadimos datos de ser el caso; de no ser el caso habrá un duplicado que se
            # eliminará mediante un conjunto/set ({})

            redes = set([agencia["agency_name"]])
            operadores = set([operador])
            refs = set([parada["stops"]["stop_id"]])
            gtfsIds = set([parada["stops"]["stop_id"]])
            refsRutas = set([ruta["route_short_name"]])

            redExistente = colision["tags"].get("network",
                agencia["agency_name"]).split(";")
            operadorExistente = colision["tags"].get("operator",
                operador).split(";")
            refExistente = tagsParada.get("ref",
                parada["stops"]["stop_id"]).split(";")
            gtfsIdExistente = tagsParada.get("gtfs_id",
                parada["stops"]["stop_id"]).split(";")
            refsRutasExistente = colision["tags"].get("route_ref",
                ruta["route_short_name"]).split(";")

            redes.update(redExistente)
            operadores.update(operadorExistente)
            refs.update(refExistente)
            gtfsIds.update(gtfsIdExistente)
            refsRutas.update(refsRutasExistente)

            redParada = ";".join(redes)
            operadorParada = ";".join(operadores)
            refParada = ";".join(refs)
            gtfsIdParada = ";".join(gtfsIds)
            referenciaRutas = ";".join(refsRutas)

            # redParada = ";".join({
            #     agencia["agency_name"],
            #     colision["tags"].get("network", agencia["agency_name"])
            # })
            # operadorParada = ";".join({
            #     operador,
            #     colision["tags"].get("operator", operador)
            # })
            # refParada = ";".join({
            #     parada["stops"]["stop_id"],
            #     colision["tags"].get("ref", parada["stops"]["stop_id"])
            # })
            # gtfsIdParada = ";".join({
            #     parada["stops"]["stop_id"],
            #     colision["tags"].get("gtfs_id", parada["stops"]["stop_id"])
            # })

            # route_refs es una particularmente especial
            # colision["tags"]["route_ref"] = colision["tags"].get("route_ref", [])
            # if colision["tags"]["route_ref"]:
            #     colision["tags"]["route_ref"] = colision["tags"]["route_ref"].split(";")
            # colision["tags"]["route_ref"].append(ruta["route_short_name"])
            # referenciaRutas = ";".join(set(colision["tags"]["route_ref"]))

            # Agregamos las etiquetas ya procesadas a las etiquetas de la paradas
            tagsParada["network"] = redParada
            tagsParada["operator"] = operadorParada
            tagsParada["gtfs_id"] = gtfsIdParada
            tagsParada["ref"] = refParada
            tagsParada["route_ref"] = referenciaRutas

            for k, v in list(tagsParada.items()):
                tag = ET.Element("tag", {"k": str(k), "v": str(v)})
                nodoParada.append(tag)

            # Añadimos el nodo a la relación de ruta (que ya está en el nodo create)
            relacionRuta.append(ET.Element("member", {
                "type": "node",
                "ref": str(colision["attrib"]["id"]),
                "role": "platform",
            }))
            # Añadimos el nodo a lo que se creará
            elementosAModificar.append(nodoParada)

        # Creamos una nueva parada
        else:
            # Creamos el nodo
            nodoParada = ET.Element("node", {
                "id": str(-i),
                "lat": str(lat),
                "lon": str(lon),
            })

            # Añadimos las etiquetas al nodo
            tagsParada = {
                "bus": "yes",
                "gtfs_id": parada["stops"]["stop_id"],
                "highway": "bus_stop",
                "name": parada["stops"]["stop_name"],
                "network": agencia["agency_name"],
                "operator": operador,
                "public_transport": "platform",
                "ref": parada["stops"]["stop_id"],
                "route_ref": ruta["route_short_name"],
            }
            for k, v in list(tagsParada.items()):
                tag = ET.Element("tag", {"k": str(k), "v": str(v)})
                nodoParada.append(tag)

            # Añadimos el nodo a la relación de ruta (que ya está en el nodo create)
            relacionRuta.append(ET.Element("member", {
                "type": "node", "ref": str(-i), "role": "platform",
            }))

            # Añadimos el nodo a lo que se creará
            elementosACrear.append(nodoParada)

        print(f"Parada #{i-offset} procesada correctamente")
        print(f"Durmiendo por {SEG_DESCANSO_ENTRE_PETIC} segundos...")
        time.sleep(SEG_DESCANSO_ENTRE_PETIC)

    # Añadimos la relación de ruta a las cosas que crear
    elementosACrear.append(relacionRuta)

    if os.path.exists(rutaOsmChange):
        os.remove(rutaOsmChange)

    xml = generarOsmchange(elementosACrear, elementosAModificar, elementosABorrar)
    xml.write(rutaOsmChange, encoding="utf-8",
              xml_declaration=True, short_empty_elements=True)

    print(f'Archivo "{rutaOsmChange}" creado correctamente.')
    pausa()


def seleccionarOpcion(opciones,
                      texto: str = "Elige una opción:",
                      alinearSeleccionACero=True,
                      limpiarPantallaAlListar=True):
    if limpiarPantallaAlListar:
        limpiarPantalla()

    mostrarMenu(opciones, texto)
    seleccion = sinput("/> ", tipoClase=int,
                       rangoValido=(1, len(opciones)+1))

    # Si la selección es la última opción, entonces se seleccionó "Salir"
    if seleccion == len(opciones)+1:
        seleccion = -1
    elif alinearSeleccionACero:
        seleccion -= 1

    return seleccion


def seleccionarParada(ruta, paradas):
    limpiarPantalla()
    paradasConNombre = [
        f'{ruta["route_short_name"]} - {x["stops"]["stop_name"]}'
        for x in paradas
    ]

    seleccion = seleccionarOpcion(
        paradasConNombre,
        "Elige una parada para mostrar sus horarios:",
        limpiarPantallaAlListar=False)

    return seleccion


def menuHorarios(ruta, viaje, paradas):
    salidaSolicitada = False
    while not salidaSolicitada:
        seleccion = seleccionarParada(ruta, paradas)

        if seleccion == -1:
            salidaSolicitada = True
            continue

        # Asignamos la parada que se solicitó para procesamiento
        parada = paradas[seleccion]

        # En resumen:
        # - Necesito calcular esquemas de horas posteriores
        #   en base a la frecuencia de paso, es decir:
        #   - Si el primer bus pasa a las 5:00, y la frecuencia de paso
        #     es de 12 minutos, hay que calcular el tiempo de llegada
        #     para las paradas donde llega a las 5:12 en su primera corrida
        #     (5 am + 12 o el tiempo de frecuencia que queramos consultar)
        #     NOTE: Podríamos pedir elegir una parada y calcular
        #           todos los horarios que hay en dicha parada
        #     NOTE 2: Hay que ver cómo nos peleamos con frequencies
        #             para lidiar con las frecuencias variables (como las de SITEUR)

        # Obtenemos los datos de la frecuencia para el cálculo de las paradas
        frecuenciasViaje = frequencies[viaje["trip_id"]]
        # Lista de los textos de los horarios
        frecuenciasParada = []

        for frecuencia in frecuenciasViaje:
            horaInicioDateTime, deltaPosicionParada, minutos = \
                obtenerHoraDeInicioYDelta(parada, frecuencia)

            for i, minutosFrecuencia in enumerate(minutos):
                nuevaHora = horaInicioDateTime + \
                    deltaPosicionParada + (minutosFrecuencia * i)
                # Creamos el tablero y lo agregamos a la lista
                texto = f"{nuevaHora.strftime('%H:%M:%S')}"
                frecuenciasParada.append(texto)

        listar(
            frecuenciasParada, 'Horarios de la parada "{}":'.format(
                parada['stops']['stop_name']))


def menuParadas(paradas: list, ruta: dict, viaje: dict, agencia: dict, operador: str):
    """
    Nuevo menú para ver datos sobre las
    paradas de la ruta seleccionada
    """
    salidaSolicitada = False
    while not salidaSolicitada:
        opciones = [
            "Seleccionar parada",
            "Ver lista de paradas",
            "Ver paradas con coordenadas",
            "Ver horarios de paradas",
            "Crear una relación de bus junto con paradas de esta ruta (formato OsmChange)",
            "Verificar colisiones de paradas de esta ruta con paradas existentes en OSM",
            "Generar wikitexto de paradas con coordenadas en GMS",
        ]
        texto = f'== Ruta {ruta["route_long_name"]}: {viaje["trip_headsign"]} =='
        seleccion = seleccionarOpcion(opciones, texto, alinearSeleccionACero=False)

        if seleccion == -1:
            salidaSolicitada = True
            continue

        # Solo se quieren ver las paradas por nombre
        elif seleccion == 2:
            paradasConNombre = [
                f'{x["stops"]["stop_id"]}: {x["stops"]["stop_name"]}'
                for x in paradas
            ]
            listar(paradasConNombre, "Paradas:")

        # Se desea ver las coordenadas de las paradas con sus nombres
        elif seleccion == 3:
            paradasConCoordenadas = [
                f'{x["stops"]["stop_id"]} - {x["stops"]["stop_lat"]},{x["stops"]["stop_lon"]} - {x["stops"]["stop_name"]}'
                for x in paradas
            ]
            listar(paradasConCoordenadas, "Paradas con coordenadas:")

        # Se quieren conocer los horarios de una determinada parada
        elif seleccion == 4:
            menuHorarios(ruta, viaje, paradas)

        # Se quiere un archivo osc para añadirlo a OpenStreetMap
        elif seleccion == 5:
            generarOsmchangeDeRutaGtfs(
                operador, agencia, ruta, viaje, paradas)

        elif seleccion == 6:
            verificarColisionesDeParadasGtfsConOsm(paradas, ruta, agencia,
                                                   generarReporte=True)

        elif seleccion == 7:
            def decAgmsXY(x, y):
                x = decAgms(x)
                y = decAgms(y)
                x[-1] = "N" if x[-1] else "S"
                y[-1] = "W" if y[-1] else "E"
                x_txt = "|".join([str(i) for i in x])
                y_txt = "|".join([str(i) for i in y])
                coords_txt = "|".join([x_txt, y_txt])
                return coords_txt

            def decAgms(n):
                positive = n < 0
                n = -n if n < 0 else n
                coords = [math.floor(n)]
                mod1 = (n - coords[0]) * 60
                coords.append(math.floor(mod1))
                mod2 = (mod1 - coords[1]) * 60
                coords.append(round(mod2, 3))
                # mod3 = (mod2 - coords[2]) * 60
                # coords.append(math.floor(mod3))
                coords.append(positive)
                return coords

            formato = "{{Coord|%s}} %s"
            paradasConCoordenadas = [
                formato % (decAgmsXY(float(x["stops"]["stop_lat"]), float(x["stops"]["stop_lon"])), x["stops"]["stop_name"])
                for x in paradas
            ]
            listar(paradasConCoordenadas, "")


def menuViajes(ruta: dict, viajes: list, agencia: dict, operador: str):
    salidaSolicitada = False
    while not salidaSolicitada:
        # Los ordenamos por id
        viajes = sorted(viajes, key=lambda x: x["trip_id"], reverse=True)
        opciones = [
            f"{x['trip_headsign']} [{x['service_id']}]"
            for x in viajes
        ]
        opciones.append("Mostrar JSON de los viajes")
        texto = f'== Ruta {ruta["route_long_name"]} =='
        # Pedimos elegir un viaje
        seleccion = seleccionarOpcion(opciones, texto)

        if seleccion == -1:
            salidaSolicitada = True
            continue
        elif seleccion == len(viajes):
            # Para depurar
            print()
            print(json.dumps(viajes, sort_keys=True, indent=3))
            print()
            pausa()
            # Para que VSCode guarde estos comentarios en el bloque de este while
            continue

        # Asignamos el viaje que seleccionó el usuario
        viaje = viajes[seleccion]
        # Obtenemos los tiempos de parada asociadas al id de viaje
        horarioParadas = stop_times[viaje["trip_id"]]
        # Obtenemos las paradas asociadas al id de parada
        paradas = ordenarParadas(horarioParadas)
        paradas = ajustarHorariosDeParadas(paradas)

        menuParadas(paradas, ruta, viaje, agencia, operador)


def menuRutas(agencia: dict, operador: str):
    salidaSolicitada = False
    while not salidaSolicitada:
        # Obtenemos las rutas que provee esta agencia
        rutas_agencia = list(routes[agencia["agency_id"]].values())
        # rutas_agencia = rutas_agencia[:20]
        rutas_agencia = sorted(rutas_agencia, key=dividirRuta)
        # Pedimos que selecciona una ruta de la agencia
        listadoNombresRuta = []
        for r in rutas_agencia:
            nombre_largo = str(r['route_long_name'])
            partes = nombre_largo.split(" - ", 1)
            if len(partes) > 1:
                nombre_largo = partes[1].strip()
            listadoNombresRuta.append(f"%-18s %s" % (r['route_short_name'], nombre_largo))
        seleccion = seleccionarOpcion(listadoNombresRuta, "Elige una ruta:")

        if seleccion == -1:
            salidaSolicitada = True
            continue

        ruta = rutas_agencia[seleccion]
        # Obtenemos los viajes que ofrece la ruta
        viajes = list(trips[ruta["route_id"]].values())

        menuViajes(ruta, viajes, agencia, operador)


def menuAgencias(agencias: list, operador: str):
    salidaSolicitada = False
    while not salidaSolicitada:
        # Pedimos que seleccione una agencia
        seleccion = seleccionarOpcion(
            [x["agency_name"] for x in agencias], "Elige una agencia:")

        if seleccion == -1:
            salidaSolicitada = True
            continue

        # Obtenemos los detalles de la agencia seleccionada
        agencia = agencias[seleccion]

        menuRutas(agencia, operador)


def menuGtfs():
    salidaSolicitada = False
    while not salidaSolicitada:
        seleccion = seleccionarOpcion(CONJUNTOS_GTFS, "Elige un conjunto de datos GTFS:")

        if seleccion == -1:
            salidaSolicitada = True
            continue

        operadorSeleccionado = CONJUNTOS_GTFS[seleccion]

        # Obtenemos los datos del conjunto seleccionado

        rutaAgency = os.path.join(RUTA_DATOS_GTFS,
                                  operadorSeleccionado, "agency.txt")
        rutaRoutes = os.path.join(RUTA_DATOS_GTFS,
                                  operadorSeleccionado, "routes.txt")
        rutaTrips = os.path.join(RUTA_DATOS_GTFS,
                                 operadorSeleccionado, "trips.txt")
        rutaFrequencies = os.path.join(RUTA_DATOS_GTFS,
                                       operadorSeleccionado, "frequencies.txt")
        rutaShapes = os.path.join(RUTA_DATOS_GTFS,
                                  operadorSeleccionado, "shapes.txt")
        rutaStops = os.path.join(RUTA_DATOS_GTFS,
                                 operadorSeleccionado, "stops.txt")
        rutaStopTimes = os.path.join(RUTA_DATOS_GTFS,
                                     operadorSeleccionado, "stop_times.txt")

        # Establecemos estas como globales para establecerlas para el resto del programa
        global agency, routes, trips, frequencies, shapes, stops, stop_times

        agency = obtenerAgencias(rutaAgency)
        if "etran" in operadorSeleccionado:
            routes = obtenerRutas(rutaRoutes, quitarTexto=True)
        else:
            routes = obtenerRutas(rutaRoutes)
        trips = obtenerViajes(rutaTrips)
        frequencies = obtenerFrecuencias(rutaFrequencies)
        shapes = obtenerTrazos(rutaShapes)
        stops = obtenerParadas(rutaStops)
        stop_times = obtenerHorariosDeParada(rutaStopTimes)

        agencias = list(agency.values())
        menuAgencias(agencias, operadorSeleccionado)


def menuDepuracion():
    salidaSolicitada = False
    opciones = [
        "Buscar una parada en la coordenada ingresada y mostrar lo obtenido en pantalla",
        "Buscar relaciones de ruta duplicadas",
        "Buscar rutas existentes en Jalisco",
        "Listar paradas de autobús en Jalisco con ref",
        "Realizar consulta overpass",
        #"Reparar operador roto (quitar el S;e;t;r;a;n;s)",
    ]
    while not salidaSolicitada:
        seleccion = seleccionarOpcion(opciones, alinearSeleccionACero=False)

        if seleccion == -1:
            salidaSolicitada = True
            continue

        elif seleccion == 1:
            lat = sinput("Ingresa la latitud: ", tipoClase=float)
            lon = sinput("Ingresa la longitud: ", tipoClase=float)
            resultado = verificarColisionDeParadaEnCoordenadas(lat, lon, incluirRespuestaCruda=True)
            limpiarPantalla()
            print(json.dumps(resultado, indent=2))
            print()
            pausa()

        elif seleccion == 2:
            peticionOverpass = """[out:json];"""
            peticionOverpass  = """area[name="Jalisco"];"""
            peticionOverpass += """relation["route"="bus"]["ref"~".+"](area);"""
            peticionOverpass += """out meta;"""
            rutas = {}

            print("Realizando petición...")
            respuesta = json.loads(consultaOverpass(peticionOverpass))
            print("Petición completada. Procesando resultados...")

            if respuesta["elements"]:
                for relacion in respuesta["elements"]:
                    # Guardamos el ref para comodidad
                    ref = relacion["tags"]["ref"]
                    # Obtenemos la lista de rutas
                    # Si no hay devolvemos una lista vacía
                    variantesEncontradas = rutas.get(ref, [])
                    variantesEncontradas.append(relacion)
                    # Asignamos la lista creada u obtenida al diccionario
                    rutas[ref] = variantesEncontradas

            print("Resultados procesados. Listando:")
            
            for ruta in rutas.values():
                if len(ruta) > 1:
                    for r in ruta:
                        print(f'{ruta[0]["tags"]["ref"]} duplicada. Detalles:')
                        print(json.dumps(r["tags"], indent=2))
                        pausa()

        elif seleccion == 3:
            peticionOverpass = """[out:json];"""
            peticionOverpass += """area[name="Jalisco"];"""
            peticionOverpass += """relation["route"="bus"]["ref"~".+"](area);"""
            peticionOverpass += """out meta;"""

            respuesta = json.loads(consultaOverpass(peticionOverpass))

            if respuesta["elements"]:
                for relacion in respuesta["elements"]:
                    print(f'Detalles de {relacion["tags"]["ref"]}:')
                    print(json.dumps(relacion["tags"], indent=2))
                    pausa()
        
        elif seleccion == 4:
            peticionOverpass = '[out:json];'
            peticionOverpass += 'area[name="Jalisco"];'
            peticionOverpass += 'node["highway"="bus_stop"]["ref"~".+"][operator](area);'
            peticionOverpass += 'out meta;'

            respuesta = json.loads(consultaOverpass(peticionOverpass))

            if respuesta["elements"]:
                for nodo in respuesta["elements"]:
                    if nodo["tags"]["operator"].find(";") != -1:
                        nodo["tags"]["operator"] = "Setran"
                        print(f'Detalles de {nodo["tags"]["ref"]}:')
                        print(json.dumps(nodo["tags"], indent=2))
                        pausa()

        elif seleccion == 5:
            peticionOverpass = input("Ingresa la petición overpass: ")
            respuesta = json.loads(consultaOverpass(peticionOverpass))
            print(respuesta["elements"])
            pausa()



def menuPrincipal():
    salidaSolicitada = False
    opciones = [
        "Menú GTFS",
        "Depuración",
    ]
    while not salidaSolicitada:
        seleccion = seleccionarOpcion(opciones, alinearSeleccionACero=False)

        if seleccion == -1:
            salidaSolicitada = True
            continue

        elif seleccion == 1:
            menuGtfs()

        elif seleccion == 2:
            menuDepuracion()


def main():
    menuPrincipal()

    return 0


if __name__ == "__main__":
    main()
