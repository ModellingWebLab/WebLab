var gulp = require('gulp');
var sass = require('gulp-sass');
var watchify = require('watchify');
var browserify = require('browserify');
var source = require('vinyl-source-stream');
var buffer = require('vinyl-buffer');
var log = require('fancy-log');
var sourcemaps = require('gulp-sourcemaps');
var assign = require('lodash.assign');

var config = {
  js: {
    src: './js/main.js',
    outputDir: './build/',
    mapDir: './maps/',
  },
  sass: {
    src: './sass/**/*.scss',
    dest: './css',
    include: ['./js/visualizers/']
  }
}

gulp.task('sass', function () {
  return gulp.src(config.sass.src)
    .pipe(sass({includePaths: config.sass.include}))
    .pipe(sass().on('error', sass.logError))
    .pipe(gulp.dest(config.sass.dest));
});


var browserified = function() {
  return browserify({
    cache: {},
    packageCache: {},
    entries: [config.js.src],
    debug: true,
    transform: []
  });
};
var watchified = watchify(browserified());

var bundle = function(pkg) {
  return pkg.bundle()
      .pipe(source(config.js.src))
      .pipe(buffer())
      .pipe(sourcemaps.init({ loadMaps : true }))
      .pipe(sourcemaps.write(config.js.mapDir))
      .pipe(gulp.dest(config.js.outputDir));
};
gulp.task('js', bundle.bind(null, browserified()));
 

gulp.task('watch', function () {
  gulp.watch(config.sass.src, gulp.series('sass'));
  // subscribe to JS file updates.
  // bundle() must be called in order to start emitting update events
  bundle(watchified);
  watchified.on('update', bundle.bind(null, watchified));
  watchified.on('log', log);
});


gulp.task('default', gulp.series(gulp.parallel('sass', 'js')));
