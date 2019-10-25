'''
Hyounguk Shon
08-Oct-2019

Usage: spark-submit kmeans.py [file.txt] [k_value]

k-Means Clustering algorithm.

Example text file: http://www.di.kaist.ac.kr/~swhang/ee412/kmeans.txt
'''

import sys
import os
from pyspark import SparkConf, SparkContext
import numpy as np
import time
import itertools

def parse(l):
    '''
    Arg:
        l (str)
    Return: 
        A np.ndarray vector.
    '''
    result = l.split(' ')
    assert '' not in result
    result = map(float, result)
    result = np.array(result)
    return result

def distance(x, y):
    '''
    Calculate Euclidean distance between vectors x and y.
    Args:
        x (np.ndarray): a vector
        y (np.ndarray): a vector
    Returns:
        A scalar distance value.
    '''
    x = np.array(x)
    y = np.array(y)
    assert x.shape == y.shape
    return np.linalg.norm(x-y)

def minimum_dist_from_points(q, points):
    '''
    Find minimum euclidean distance between q and a set of points.
    Args:
        q (np.ndarray): a point vector
        points (list): a list of point vectors
    Returns:
        A scalar distance value.
    '''
    dist = np.inf
    for p in points:
        dist0 = distance(p, q)
        if dist0 < dist:
            dist = dist0
    return dist

def initial_centroids(points, k, always_include_first_point=True):
    '''
    Choose k initial centroids for k-Means algorithm.
    Args:
        points (list): a list of points
        k (int): number of initial centroids.
        always_include_first_point (bool): If True, initial centroid is first point.
    Returns:
        A list of initial centroids.
    '''
    assert isinstance(k, int) and k>0
    centroids = []

    ''' pick the first point '''
    if always_include_first_point:
        centroids.append(points.pop(0))
    else: 
        i = np.random.randint(0, len(points)-1)
        centroids.append(points.pop(i))

    ''' pick rest of the points '''
    while len(centroids) < k:
        index_list = list(range(len(points)))
        index_max = max(index_list, key = lambda i: minimum_dist_from_points(points[i], centroids))
        centroids.append(points.pop(index_max))

    return centroids, points

class Cluster:
    def __init__(self):
        self.points = []
        self._SUM = 0
        self._SUMSQ = 0
    
    def __len__(self):
        return len(self.points)

    def add_point(self, p):
        p = np.array(p)
        self.points.append(p)
        self._SUM += p
        self._SUMSQ += p**2
        return self

    @property
    def diameter(self):
        if len(self) > 1:
            result = max([distance(x, y) for x, y in itertools.combinations(self.points, 2)])
        else:
            result = 0.0
        return result

    @property
    def variance(self):
        N = len(self)
        return (self._SUMSQ/N) - (self._SUM/N)**2
    

def find_centroid(x, y):
    '''
    compare distance of value x and y and return value of minimum distance.
    '''
    _, xd = x
    _, yd = y

    if xd < yd:
        return x
    else:
        return y

def main():
    ''' parameters '''
    filepath = sys.argv[1]
    k = int(sys.argv[2])
    nExecuter = 8
    conf = SparkConf()
    sc = SparkContext(conf=conf)

    ''' read and parse dataset '''
    with open(filepath, 'r') as file:
        lines = file.readlines()

    points = map(parse, lines)
    centroids, _ = initial_centroids(points, k, always_include_first_point=True)

    # create k-clusters
    clusters = [Cluster() for _ in range(k)]

    # add each centroid to each cluster
    for i, centroid in enumerate(centroids):
        clusters[i].add_point(centroid)
        clusters[i].centroid = centroid

    ''' k-means algorithm '''
    # Initially choose k centroids;
    # FOR each remaining point p DO
    #     Find the centroid to which p is closest;
    #     Add p to the cluster of that centroid;
    # END;

    clusters = sc.parallelize(points, nExecuter)
    clusters = clusters.flatMap(lambda p: [(tuple(p), (i, distance(p, centroids[i]))) for i in range(len(centroids))])
    clusters = clusters.reduceByKey(lambda x, y: x if x[1] < y[1] else y)

    clusters = clusters.map(lambda (p, (i, d)): (i, p))
    clusters = clusters.groupByKey()

    # calculate diameter of each cluster by spark
    for cluster in clusters.collect():
        i, points = cluster
        print len(points)
        if len(points) > 1:
            points_RDD = sc.parallelize([(p1, p2) for p1, p2 in itertools.combinations(points, 2)], nExecuter)
            points_RDD = points_RDD.map(lambda (p1, p2): distance(p1, p2))
            points_RDD = points_RDD.reduce(lambda x, y: max(x, y))
            print points_RDD.collect()
        else:
            diameter = 0

    # for p, (c, _) in points.collect():
    #     for cluster in clusters:
    #         if np.allclose(cluster.centroid, c):
    #             cluster.add_point(p)


    # print [len(c) for c in clusters]

    ''' print average diameter of clusters '''
    # this seems too expensive
    # print np.average([c.diameter for c in clusters])

if __name__ == '__main__':

    ''' sanity check '''
    assert os.path.exists(sys.argv[1]),  'Cannot find file.'
    assert int(sys.argv[2]) > 0, 'k must be an integer greater than 0'
    
    starttime = time.time()
    main()
    print 'Executed in: {}'.format(time.time()-starttime)