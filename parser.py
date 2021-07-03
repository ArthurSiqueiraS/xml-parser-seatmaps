#!/usr/bin/env python
# coding: utf-8

"""
       Author: Arthur Siqueira e Silva
  Description: This script takes an XML file containing seatmap information as input and outputs
               it's relevant data into a standard JSON format.
"""

import xml.etree.ElementTree as ET
import sys
import re
import json

""" get_namespace

  Gets XML namespace from element

"""
def get_namespace(element):
  ns = re.match(r'\{.*\}', element.tag)
  return ns.group(0) if ns else ''

""" abort

  Prints and error message and interrupts execution

"""
def abort(msg):
  print("\033[91mERROR:\033[0m " + msg)
  exit()

""" xml_to_json

  Parses the XML file into a json output

"""
def xml_to_json(path):
  try:
    tree = ET.parse(path)
  except FileNotFoundError:
    abort("File not found")
  except ET.ParseError:
    abort("Invalid file format")

  root = tree.getroot()

  if 'xmlsoap' in root.tag:
    return parse_from_soap(root)
  elif 'iata' in root.tag:
    return parse_from_iata(root)
  else:
    abort('XML format not supported')

""" parse_from_soap

  Parses a soap type XML tree into and returns the relevant data in a standard structure

"""
def parse_from_soap(root):
  global ns
  body = root[0][0]
  # Saves namespace for iterations
  ns = get_namespace(body)
  result = {}

  # Iterates over seatmap responses
  for response in body.iter(ns+'SeatMapResponse'):
    # Flight info
    flight = response.find(ns+'FlightSegmentInfo')
    flight_id = flight.get('FlightNumber')
    flight_departure = flight.get('DepartureDateTime')

    rows = {}

    seatmap = response.find(ns+'SeatMapDetails')
    # Iterates over flight cabin rows
    for row in seatmap.iter(ns+'RowInfo'):
      row_data = soap_row_info(row)
      rows[row_data['row_id']] = row_data

    result[flight_id] = format_flight(flight_id, flight_departure, rows)

  return result

""" soap_row_info

  Receives a row XML element and extracts it's relevant data into a standard format

"""
def soap_row_info(row):
  cabin_class = row.get('CabinType')
  row_number = row.get('RowNumber')

  seats = [soap_seat_info(seat) for seat in row.iter(ns+'SeatInfo')]

  return format_row(row_number, cabin_class, seats)

""" soap_seat_info

  Receives a seat XML element and extracts it's relevant data into a standard format

"""
def soap_seat_info(seat):
  summary = seat.find(ns+'Summary')
  seat_id = summary.get('SeatNumber')
  available = summary.get('AvailableInd') == 'true'
  # Get seat features
  seat_type = []
  for feature in seat.iter(ns+'Features'):
    try:
      seat_type.append(feature.get('extension'))
    except KeyError:
      seat_type.append(feature.text)

  # Get fee and tax prices
  if available:
    fee = seat.find(ns+'Service').find(ns+'Fee')
    amount = int(fee.get('Amount'))
    precision = int(fee.get('DecimalPlaces'))
    currency = fee.get('CurrencyCode')
    seat_price = format_price(amount, currency, precision)

    total_taxes = sum([int(tax.get('Amount')) for tax in fee.findall(ns+'Tax')])
    taxes = format_price(total_taxes)
  else:
    seat_price = format_price(0)
    taxes = format_price(0)

  return format_seat(seat_id, seat_type, available, seat_price, taxes)

""" parse_from_iata

  Parses an iata type XML tree into and returns the relevant data in a standard structure

"""
def parse_from_iata(root):
  global ns
  ns = get_namespace(root)
  # fligts_ref = { flight.get(eg: )
  offers = { offer.get('OfferItemID'): iata_offer_info(offer) for offer in root.iter(ns+'ALaCarteOfferItem') }
  return {}

def iata_offer_info(offer):
  id = offer.get('OfferItemID')
  # price_el = offer.find('UnitPriceDetail').find('TotalAmount').find('SimpleCurrencyPrice')
  # amount = price_el.text
  # currency = price_el.get('Code')
  # price = format_price(amount, currency)

""" format_flight

  Formats flight data to a standard dict format

"""
def format_flight(id, departure, rows):
  return {
    'flight_id': id,
    'departure': departure,
    'rows': rows
  }

""" format_row

  Formats a flight row data to a standard dict

"""
def format_row(id, cabin_class, seats=[]):
  return {
    'row_id': id,
    'cabin_class': cabin_class,
    'seats': seats
  }

""" format_seat

  Formats seat data to a standard dict

"""
def format_seat(id, seat_type, available, price='N/A', taxes='N/A'):
  return {
    'seat_id': id,
    'type': seat_type,
    'available': available,
    'price': price,
    'taxes': taxes
  }

""" format_price

  Returns the price in a readable format

"""
def format_price(amount, currency='', precision=2):
  if amount > 0:
    return '{price: .{prec}f} {curr}'.format(price = (amount / (10**precision)), prec = precision, curr = currency)
  else:
    return 'N/A'

if __name__ == "__main__":
  try:
    path = sys.argv[1]
  except IndexError:
    # Abort if no argument passed
    abort("Must pass a file path")

  data = xml_to_json(path)
  output_filename = '{FILENAME}_parsed.json'.format(FILENAME = path.split('.')[0])

  with open(output_filename, 'w') as f:
    json.dump(data, f)


