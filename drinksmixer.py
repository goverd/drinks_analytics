#!/usr/bin/env python -tt

from bs4 import BeautifulSoup
from time import sleep
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import requests
import re
import sys


def scrape_drink_links():

    max_page = 125

    url_prefix = 'http://www.drinksmixer.com/cat/1/'
    url_postfix = '/'
    host_name = 'http://www.drinksmixer.com'

    drink_links = []
    for page in xrange(1, max_page):
        print 'Processing page #: %i' %(page)

        try:
            request = requests.get(url_prefix + str(page) + url_postfix)
            soup = BeautifulSoup(request.text, 'lxml')
            links = [link.get('href') for link in soup.find_all('a')]
            pattern= re.compile(r'^/drink\w+\.html$')
            drink_links.extend(filter(pattern.match, links))
            sleep(0.5)
        except:
            continue

    drink_links = list(set(drink_links))
    drink_links = [host_name + link for link in drink_links]
    dr_link_df = pd.DataFrame(drink_links)
    dr_link_df.columns = ['link2drink']
    dr_link_df.to_csv('drink_links.csv', sep = ',')

def scrape_drink_details(links_file = 'drink_links.csv'):
    host_name = 'http://www.drinksmixer.com'
    drink_links = pd.read_csv(links_file, index_col = 0)

    nutrients = ['calories', 'energy_kj', 'fat', 'carbohydrates', 'protein', \
                 'fiber', 'sugar', 'cholesterol', 'sodium', 'alcohol']

    drinks_df = pd.DataFrame()
    failed_links = []
    for ind, link in enumerate(drink_links.link2drink):
        print 'Processing drink #: %05i\r' %(ind + 1),
        sys.stdout.flush()

        #Attempt to get drink data, if it fails for any reason go to next drink to prevent data loss
        try:
            request = requests.get(link)
            soup = BeautifulSoup(request.text, 'lxml')

            drink_dict = {}
            #Extract name
            drink_dict['drink_name'] = [re.search(r'(.+)\srecipe$', soup.title.string.encode('ascii', 'ignore')).group(1)]

            #Extract rating information if exists
            try:
                drink_dict['rating_count'] = [int(soup.find(class_="count").string)]
                drink_dict['rating'] = [float(soup.find(style="font-size:36px; font-weight: bold;").string)]
            except AttributeError:
                drink_dict['rating_count'] = [np.nan]
                drink_dict['rating'] = [np.nan]

            #Extract ingredients
            ing_amounts = [amount.string.encode('ascii', 'ignore') for amount in soup.find_all(class_='amount')]
            ing_links = [str(tag.a['href']) for tag in soup.find(class_='ingredients').find_all(class_='name')]
            ing_links = [host_name + link for link in ing_links]
            ing_names = [tag.a.string.encode('ascii', 'ignore') for tag in soup.find(class_='ingredients').find_all(class_='name')]
            amnts_links = zip(ing_amounts, ing_links)

            drink_dict['ingredients'] = [dict(zip(ing_names, amnts_links))]
            drink_dict['ing_count'] = [len(ing_names)]

            #Extract instructions
            drink_dict['instructions'] = [soup.find(class_='RecipeDirections instructions').text.encode('ascii', 'ignore')]
            drink_dict['instr_ch_count'] = [len(drink_dict['instructions'][0])]

            #Get nutritional information if it's present
            nutr_info_missing = False
            try:
                drink_dict['serving'] = [str(soup.find(itemprop='nutrition').div.itemprop.string)[:-1]]
            except AttributeError:
                drink_dict['serving'] = [np.nan]
                nutr_info_missing = True

            for ind, nutrient in enumerate(nutrients):
                if nutr_info_missing:
                    drink_dict[nutrient] = [np.nan]
                else:
                    if nutrient == 'energy_kj' or nutrient == 'alcohol':
                        drink_dict[nutrient] = [soup.find(itemprop=nutrients[ind - 1]).next_sibling.next_sibling.encode('ascii', 'ignore')]
                    else:
                        drink_dict[nutrient] = [soup.find(itemprop=nutrient).string.encode('ascii', 'ignore')]

            #Convert scraped data for one drink to DataFrame and append to master DataFrame
            drink_df = pd.DataFrame(drink_dict)
            drinks_df = pd.concat((drinks_df, drink_df))
        except:
            print 'Scraping data failed for drink #: %05i\r' %(ind + 1)
            failed_links.append(link)
            continue

    f = pd.HDFStore('drinks_df.h5')
    f['drinks_data'] = drinks_df
    f.close()

    return failed_links

def explore_data():

    drinks_file = pd.HDFStore('drinks_df.h5')
    drinks = drinks_file['drinks_data']
    drinks_file.close()

    drinks.index = range(0, len(drinks))

    drinks = drinks.join(drinks.serving.str.extract(r'^(?P<serving_num>[\d\.]+)\s+(?P<serving_vol>\w+)\s+', expand = True))
    drinks['cal_per_serving'] = drinks.calories.astype('float')/drinks.serving_num.astype('float')

    # Get drinks with non NaN calorie counts, no outliers and with more than 10 ratings
    with_cal_info = drinks[(~drinks.cal_per_serving.isnull()) & (drinks.cal_per_serving < 200) & (drinks.rating_count > 10)]

    # Plot histogram of calories per serving
    plt.figure(1)
    plt.hist(with_cal_info.cal_per_serving, bins = 50)
    plt.grid(True)
    plt.xlabel('Calories per serving (kcal / 1 oz)')
    plt.ylabel('Number of drinks')
    xmin, xmax = plt.xlim()

    # Plot ratings vs calories per serving
    plt.figure(2)
    plt.scatter(with_cal_info.cal_per_serving, with_cal_info.rating, alpha = 0.6, edgecolors='face', color = 'r', s = 30)
    plt.grid(True)
    plt.xlabel('Calories per serving (kcal / 1 oz)')
    plt.ylabel('Rating of a drink out of 10')
    plt.xlim(xmin, xmax)

    plt.show()


def main():
    pass

if __name__ == "__main__":
    main()
