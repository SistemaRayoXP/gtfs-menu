# -*- coding: utf-8 -*-

import csv
import json
import os

def main():
    # Definimos las rutas de archivo
    gtfsp = "/home/edson/Descargas/gtfs-visualizations/gtfs/siteur/"
    ap = os.path.join(gtfsp, "agency.txt")
    rp = os.path.join(gtfsp, "routes.txt")
    tp = os.path.join(gtfsp, "trips.txt")
    sp = os.path.join(gtfsp, "shapes.txt")
    stp = os.path.join(gtfsp, "stops.txt")
    sttp = os.path.join(gtfsp, "stop_times.txt")

    # Obtenemos los datos
    agency = get_agencies(ap)
    routes = get_routes(rp)
    trips = get_trips(tp)
    shapes = get_shapes(sp)
    stops = get_stops(stp)
    stop_times = get_stop_times(sttp)

    # Mostramos la salida de las funciones
    # TODO: Eliminar esta función cuando vayamos a terminar el programa
    # data = stop_times
    data = stops

    print(json.dumps(data, sort_keys=True, indent=3))


def get_agencies(agency_file):
    agencies = {}
    data = csv2dict(agency_file)

    for agency in data:
        agency_id = agency["agency_id"]

        if not agencies.get(agency_id):
            agencies[agency_id] = {}

        agencies[agency_id] = agency

    return agencies


def get_routes(routes_file):
    routes = {}
    data = csv2dict(routes_file)

    for route in data:
        agency_id = route["agency_id"]
        route_id = route["route_id"]

        if not routes.get(agency_id):
            routes[agency_id] = {}

        if not routes[agency_id].get(route_id):
            routes[agency_id][route_id] = {}

        routes[agency_id][route_id] = route

    return routes


def get_trips(trips_file):
    trips = {}
    data = csv2dict(trips_file)

    for trip in data:
        route_id = trip["route_id"]
        trip_id = trip["trip_id"]

        if not trips.get(route_id):
            trips[route_id] = {}

        trips[route_id][trip_id] = trip

    return trips


def get_stops(stops_file):
    stops = {}
    data = csv2dict(stops_file)

    for stop in data:
        stop_id = stop["stop_id"]

        if not stops.get(stop_id):
            stops[stop_id] = {}

        stops[stop_id] = stop

    return stops


def get_stop_times(stop_times_file):
    stimes = {}
    data = csv2dict(stop_times_file)

    for stop in data:
        trip_id = stop["trip_id"]

        if not stimes.get(trip_id):
            stimes[trip_id] = {}

        stimes[trip_id] = stop

    return stimes


def get_shapes(shape_file):
    """Devuelve los trazos de ruta ordenados en un diccionario por id de
    trazo (shape_id) y número de secuencia (shape_pt_sequence)"""
    shapes = {}
    data = csv2dict(shape_file)

    for trace in data:
        shape_id = trace["shape_id"]

        if not shapes.get(shape_id):
            shapes[shape_id] = {}

        pt_seq = int(trace.pop("shape_pt_sequence"))
        shapes[shape_id][pt_seq] = trace

    return shapes


def csv2dict(file):
    """Tranforma datos crudos CSV a una lista de diccionarios
    tomando como claves la primera columna del CSV"""
    with open(file) as f:
        reader = csv.DictReader(f)
        data = [x for x in reader]

    return data


if __name__ == "__main__":
    main()
