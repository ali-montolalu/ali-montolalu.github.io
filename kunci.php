<?php
session_start();

// cek apakah yang mengakses halaman ini sudah login
    if($_SESSION['level']==""){
    header("location:index.php?pesan=gagal");
  }
    require "koneksi.php";

    if(isset($_POST['submit'])){
        $pilihan = $_POST["pilihan"];
        $id = $_POST["id"];
        $jumlah = $_POST["jumlah"];

        $score = 0;
        $benar = 0;
        $salah = 0;
        $kosong = 0;

        for($i=0;$i<$jumlah;$i++){
            $nomor = $id[$i]; // id nomor soal

            // jika user tidak memilih jawaban
            if(empty($pilihan[$nomor])){
                $kosong++;
            } else {
                // jika memilih
                $jawaban = $pilihan[$nomor];

                // cocokan jawaban dengan yang ada didatabase
                $sql = "SELECT * FROM soal WHERE id='$nomor' AND kunci='$jawaban'";
                $query = mysqli_query($koneksi,$sql) or die (mysqli_error($koneksi));

                $cek = mysqli_num_rows($query);

                if($cek){
                    // jika jawaban cocok (benar)
                    $benar++;
                } else {
                    // jika salah
                    $salah++;
                }

            }
            /*
                ----------
                Nilai 100
                ----------
                Hasil = 100 / jumlah soal * Jawaban Benar
            */

            $sql = "SELECT * FROM soal ";
            $query = mysqli_query($koneksi,$sql) or die (mysqli_error($koneksi));
            $jumlah_soal = mysqli_num_rows($query);
            $score = 100 / $jumlah_soal * $benar;
            $hasil = number_format($score,1);
        }
    }

    
?>

<!DOCTYPE html>
<html>
<head>
    <title></title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css" integrity="sha384-Vkoo8x4CGsO3+Hhxv8T/Q5PaXtkKtu6ug5TOeNV6gBiFeWPGFN9MuhOf23Q9Ifjh" crossorigin="anonymous">
    <script type="text/javascript" src="assets/fontawesome/js/all.js"></script>
</head>
<body>
    <div class="container">
<div class="card mt-5">
  <h5 class="card-header bg-danger text-white">Hasil</h5>
  <div class="card-body">
    <div class="text-center" style="font-size: 20px;">
    <td>Jumlah soal: <?=$jumlah_soal; ?> </td><br>
    <td>Benar: <?= $benar; ?> <i class= "fas fa-check-circle text-success"></i></td><br>
    <td>Salah: <?=$salah; ?> <i class= "fas fa-times-circle text-danger"></i></td><br>
    <td>Kosong: <?=$kosong; ?> <i class= "fas fa-minus-circle text-warning"></i></td><br>
    <td>Score: <?=$score; ?> </td>
    </div>
  </div>
  <div class="card-footer bg-transparent text-center">
      <a href="logout.php" class="btn btn-danger"><i class="fas fa-sign-out-alt"></i> Logout</a>
  </div>
</div>
</div>
    <!-- Optional JavaScript -->
    <!-- jQuery first, then Popper.js, then Bootstrap JS -->
    <script src="https://code.jquery.com/jquery-3.4.1.slim.min.js" integrity="sha384-J6qa4849blE2+poT4WnyKhv5vZF5SrPo0iEjwBvKU7imGFAV0wwj1yYfoRSJoZ+n" crossorigin="anonymous"></script>
    <script src="https://cdn.jsdelivr.net/npm/popper.js@1.16.0/dist/umd/popper.min.js" integrity="sha384-Q6E9RHvbIyZFJoft+2mJbHaEWldlvI9IOYy5n3zV9zzTtmI3UksdQRVvoxMfooAo" crossorigin="anonymous"></script>
    <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/js/bootstrap.min.js" integrity="sha384-wfSDF2E50Y2D1uUdj0O3uMBJnjuUD4Ih7YwaYd1iqfktj0Uod8GCExl3Og8ifwB6" crossorigin="anonymous"></script>

</body>
</html>