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
from abc import ABC, abstractmethod

class ParserXML(ABC):
  def __init__(self, root):
    """
      Initialization
    """
    self.root = root
    self.ns = ''

  def _get_namespace(self, element):
    """
      Gets XML namespace from element
    """
    ns = re.match(r'\{.*\}', element.tag)
    return ns.group(0) if ns else ''

  def _iter(self, tag, root=None):
    """
      Iterates over elements inside the given tree that match the tag
    """
    if not root:
      root = self.root
    return root.iter(self.ns + tag)

  def _find(self, el, tag):
    """
      Finds the first child of the element with the specified tag
    """
    return el.find(self.ns + tag)

  def _format_flight(self, id, date, time, rows):
    """
      Formats flight data to a standard dict format
    """
    return {
      'flight_id': id,
      'date': date,
      'time': time[:5],
      'rows': rows
    }

  def _format_row(self, id, cabin_class, seats=[]):
    """
      Formats a flight row data to a standard dic
    """
    return {
      'row_id': id,
      'cabin_class': cabin_class,
      'seats': seats
    }

  def _format_seat(self, id, seat_type, available, price='N/A', taxes='N/A'):
    """
      Formats seat data to a standard dict
    """
    return {
      'seat_id': id,
      'type': seat_type,
      'available': available,
      'price': price,
      'taxes': taxes
    }

  def _format_price(self, amount, currency='', precision=2):
    """
      Returns the price in a readable format
    """
    if amount > 0:
      return '{price: .{prec}f} {curr}'.format(price = amount, prec = precision, curr = currency).strip()
    else:
      return 'N/A'

  @abstractmethod
  def parse(self):
    """
      Parses the XML file into a json output
    """

class SoapParser(ParserXML):
  def parse(self):
    """
      Parses a soap type XML tree into and returns the relevant data in a standard structure
    """
    body = root[0][0]
    # Saves namespace for iterations
    self.ns = self._get_namespace(body)
    result = {}

    # Iterates over seatmap responses
    for response in self._iter('SeatMapResponse', body):
      # Flight info
      flight = self._find(response, 'FlightSegmentInfo')
      flight_id = flight.get('FlightNumber')
      flight_departure = flight.get('DepartureDateTime')
      [flight_date, flight_time] = flight_departure.split('T')

      seatmap = self._find(response, 'SeatMapDetails')
      # Iterates over flight cabin rows
      rows = [self.__soap_row_info(row) for row in self._iter('RowInfo', seatmap)]

      result[flight_id] = self._format_flight(flight_id, flight_date, flight_time, rows)

    return result

  def __soap_row_info(self, row):
    """
      Receives a row XML element and extracts it's relevant data into a standard format
    """
    cabin_class = row.get('CabinType')
    row_number = row.get('RowNumber')

    seats = [self.__soap_seat_info(seat) for seat in self._iter('SeatInfo', row)]

    return self._format_row(row_number, cabin_class, seats)

  def __soap_seat_info(self, seat):
    """
      Receives a seat XML element and extracts it's relevant data into a standard format
    """
    summary = self._find(seat, 'Summary')
    seat_id = summary.get('SeatNumber')
    available = summary.get('AvailableInd') == 'true'
    # Get seat features
    seat_type = []
    for feature in self._iter('Features', seat):
      feat = feature.get('extension')
      if not feat:
        feat = feature.text
      seat_type.append(feat)

    # Get fee and tax prices
    if available:
      fee = self._find(self._find(seat, 'Service'), 'Fee')
      amount = float(fee.get('Amount'))
      precision = int(fee.get('DecimalPlaces'))
      currency = fee.get('CurrencyCode')
      seat_price = self._format_price((amount / (10**precision)), currency, precision)

      total_taxes = sum([float(tax.get('Amount')) for tax in self._iter('Tax', fee)])
      taxes = self._format_price((total_taxes / (10**precision)), currency, precision)
    else:
      seat_price = self._format_price(0)
      taxes = self._format_price(0)

    return self._format_seat(seat_id, seat_type, available, seat_price, taxes)

class IataParser(ParserXML):
  def parse(self):
    """
      Parses an iata type XML tree into and returns the relevant data in a standard structure
    """
    # Sets namespace
    self.ns = self._get_namespace(self.root)
    # Collects data for flights, offers and seat definitions
    self.flights = { flight.get('SegmentKey'): self.__iata_flight_info(flight) for flight in self._iter('FlightSegment') }
    self.offers = { offer.get('OfferItemID'): self.__iata_offer_info(offer) for offer in self._iter('ALaCarteOfferItem') }
    self.seat_definitions = {}
    for seat_def in self._iter('SeatDefinition'):
      self.seat_definitions[seat_def.get('SeatDefinitionID')] = self._find(self._find(seat_def, 'Description'), 'Text').text

    # Extracts data from each seatmap
    for seat_map in self._iter('SeatMap'):
      seg_ref = self._find(seat_map, 'SegmentRef').text
      flight = self.flights.get(seg_ref)
      flight['rows'] += [self.__iata_row_info(row) for row in self._iter('Row')]

    return { flight.get('flight_id'): flight for flight in self.flights.values() }

  def __iata_flight_info(self, flight):
    """
      Receives a Flight Segment element and extracts it's relevant data into a standard format
    """
    departure_info = self._find(flight, 'Departure')
    flight_date = self._find(departure_info, 'Date').text
    flight_time = self._find(departure_info, 'Time').text
    flight_id = self._find(self._find(flight, 'MarketingCarrier'), 'FlightNumber').text
    return self._format_flight(flight_id, flight_date, flight_time, [])

  def __iata_offer_info(self, offer):
    """
      Receives an Offer Item element and extracts it's relevant data into a standard format
    """
    id = offer.get('OfferItemID')
    total_amount_el = self._find(self._find(offer, 'UnitPriceDetail'), 'TotalAmount')
    price_el = self._find(total_amount_el, 'SimpleCurrencyPrice')
    amount = float(price_el.text)
    currency = price_el.get('Code')
    price = self._format_price(amount, currency)
    return price

  def __iata_row_info(self, row):
    """
      Receives a Row element and extracts it's relevant data into a standard format
    """
    row_number = self._find(row, 'Number').text
    seats = [self.__iata_seat_info(seat, row_number) for seat in self._iter('Seat', row)]
    return self._format_row(row_number, 'Common', seats)

  def __iata_seat_info(self, seat, row_number):
    """
      Receives a Seat element and Row number and extracts it's relevant data into a standard format
    """
    col = self._find(seat, 'Column').text
    seat_id = row_number + col

    available = False
    seat_type = []
    # Lists referenced seat definitions
    for seat_def_ref in self._iter('SeatDefinitionRef', seat):
      key = seat_def_ref.text
      if key == 'SD4':
        # SD4 is definition AVAILABLE
        available = True
      else:
        seat_type.append(self.seat_definitions.get(key))

    if available:
      offer_ref = self._find(seat, 'OfferItemRefs')
      try:
        price = self.offers[offer_ref.text]
      except AttributeError:
        # Offer might not be referenced
        price = self._format_price(0)
    else:
      price = self._format_price(0)

    return self._format_seat(seat_id, seat_type, available, price, self._format_price(0))

def abort(msg):
  """
    Prints an error message and interrupts execution
  """
  print("\033[91mERROR:\033[0m " + msg)
  exit()

if __name__ == "__main__":
  try:
    path = sys.argv[1]
  except IndexError:
    # Abort if no argument passed
    abort("Must pass a file path")

  try:
    tree = ET.parse(path)
  except FileNotFoundError:
    abort("File not found")
  except ET.ParseError:
    abort("Invalid file format")

  root = tree.getroot()

  if 'xmlsoap' in root.tag:
    parser = SoapParser(root)
  elif 'iata' in root.tag:
    parser = IataParser(root)
  else:
    abort('XML format not supported')

  data = parser.parse()
  output_filename = '{FILENAME}_parsed.json'.format(FILENAME = path.split('.')[0])

  with open(output_filename, 'w') as f:
    json.dump(data, f)


